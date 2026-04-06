#!/usr/bin/env python3
"""
Google Cloud Storage Backup Script
==================================
This script uploads backup files to Google Cloud Storage.
It supports folder organization (daily/weekly/monthly) and cold storage for long-term retention.

Usage:
    python gcs_backup.py --upload                    # Upload latest local backups
    python gcs_backup.py --upload --folder daily    # Upload to daily/ folder
    python gcs_backup.py --list                      # List GCS backups
    python gcs_backup.py --list --folder daily       # List backups in daily/ folder
    python gcs_backup.py --restore <file>           # Download and restore from GCS
    python gcs_backup.py --cleanup 30               # Delete backups older than 30 days

Environment Variables:
    GCS_BUCKET_NAME        - GCS bucket name (e.g., ym-academy-backups)
    GCS_CREDENTIALS_PATH   - Path to GCP service account JSON key file
    GCS_PROJECT_ID         - GCP project ID (optional)
    GCS_STORAGE_CLASS      - Storage class (STANDARD, NEARLINE, COLDLINE, ARCHIVE)
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GCSBackup:
    """Google Cloud Storage Backup Manager"""
    
    def __init__(self):
        self.bucket_name = os.getenv('GCS_BUCKET_NAME', 'ym-academy-backups')
        self.credentials_path = os.getenv('GCS_CREDENTIALS_PATH', '/api/gcs-credentials.json')
        self.storage_class = os.getenv('GCS_STORAGE_CLASS', '')
        self.backup_dir = Path('/api/backups')
        
        # Check if GCS is configured
        self.gcs_configured = bool(self.bucket_name and os.path.exists(self.credentials_path))
        
        if self.gcs_configured:
            try:
                from google.cloud import storage
                self.client = storage.Client.from_service_account_json(self.credentials_path)
                self.bucket = self.client.bucket(self.bucket_name)
                logger.info(f"Connected to GCS bucket: {self.bucket_name}")
            except Exception as e:
                logger.error(f"Failed to connect to GCS: {e}")
                self.gcs_configured = False
        else:
            logger.warning("GCS not configured. Set GCS_BUCKET_NAME and GCS_CREDENTIALS_PATH")
    
    def upload_file(self, local_path: Path, destination_name: str, folder: str = '') -> bool:
        """Upload a file to GCS with optional folder path and storage class"""
        if not self.gcs_configured:
            logger.error("GCS not configured")
            return False
        
        if not local_path.exists():
            logger.error(f"File not found: {local_path}")
            return False
        
        try:
            # Build blob path with folder
            if folder:
                blob_name = f"backups/{folder}/{destination_name}"
            else:
                blob_name = f"backups/{destination_name}"
            
            blob = self.bucket.blob(blob_name)
            
            # Set storage class if specified (for cold storage)
            if self.storage_class:
                blob.storage_class = self.storage_class
                logger.info(f"Setting storage class: {self.storage_class}")
            
            blob.upload_from_filename(str(local_path))
            
            file_size = local_path.stat().st_size / (1024 * 1024)  # MB
            logger.info(f"Uploaded {destination_name} to GCS/{folder or 'root'} ({file_size:.2f} MB)")
            return True
        except Exception as e:
            logger.error(f"Failed to upload {local_path}: {e}")
            return False
    
    def upload_latest_backups(self, folder: str = '') -> int:
        """Upload the latest backup files to GCS"""
        if not self.gcs_configured:
            logger.error("GCS not configured")
            return 0
        
        if not self.backup_dir.exists():
            logger.error(f"Backup directory not found: {self.backup_dir}")
            return 0
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        uploaded = 0
        
        # Find and upload latest database backup
        db_backups = sorted(self.backup_dir.glob("db_backup_*.sql.gz"), key=os.path.getmtime, reverse=True)
        if db_backups:
            latest_db = db_backups[0]
            dest_name = f"db_{timestamp}.sql.gz"
            if self.upload_file(latest_db, dest_name, folder):
                uploaded += 1
        
        # Find and upload latest uploads backup
        uploads_backups = sorted(self.backup_dir.glob("uploads_backup_*.tar.gz"), key=os.path.getmtime, reverse=True)
        if uploads_backups:
            latest_uploads = uploads_backups[0]
            dest_name = f"uploads_{timestamp}.tar.gz"
            if self.upload_file(latest_uploads, dest_name, folder):
                uploaded += 1
        
        logger.info(f"Uploaded {uploaded} backup(s) to GCS/{folder or 'root'}")
        return uploaded
    
    def list_backups(self, prefix: str = "backups/") -> List[dict]:
        """List all backups in GCS"""
        if not self.gcs_configured:
            logger.error("GCS not configured")
            return []
        
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            backups = []
            for blob in blobs:
                backups.append({
                    'name': blob.name,
                    'size': blob.size / (1024 * 1024),  # MB
                    'created': blob.time_created.isoformat() if blob.time_created else None,
                    'storage_class': blob.storage_class
                })
            return backups
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []
    
    def download_file(self, blob_name: str, destination: Path) -> bool:
        """Download a file from GCS"""
        if not self.gcs_configured:
            logger.error("GCS not configured")
            return False
        
        try:
            blob = self.bucket.blob(blob_name)
            blob.download_to_filename(str(destination))
            logger.info(f"Downloaded {blob_name} to {destination}")
            return True
        except Exception as e:
            logger.error(f"Failed to download {blob_name}: {e}")
            return False
    
    def delete_old_backups(self, days: int = 30, folder: str = '') -> int:
        """Delete backups older than specified days, optionally in a specific folder"""
        if not self.gcs_configured:
            logger.error("GCS not configured")
            return 0
        
        from datetime import timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Build prefix based on folder
        if folder:
            prefix = f"backups/{folder}/"
        else:
            prefix = "backups/"
        
        deleted = 0
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            for blob in blobs:
                # Handle both timezone-aware and naive datetimes
                blob_time = blob.time_created
                if blob_time:
                    if blob_time.tzinfo is None:
                        blob_time = blob_time.replace(tzinfo=timezone.utc)
                    if blob_time < cutoff:
                        blob.delete()
                        logger.info(f"Deleted old backup: {blob.name}")
                        deleted += 1
        except Exception as e:
            logger.error(f"Failed to delete old backups: {e}")
        
        return deleted


def main():
    parser = argparse.ArgumentParser(description='Google Cloud Storage Backup Tool')
    parser.add_argument('--list', action='store_true', help='List backups in GCS')
    parser.add_argument('--upload', action='store_true', help='Upload latest backups to GCS')
    parser.add_argument('--restore', type=str, help='Download and restore a backup from GCS')
    parser.add_argument('--cleanup', type=int, default=0, help='Delete backups older than N days')
    parser.add_argument('--folder', type=str, default='', 
                       help='Folder for backup (daily/weekly/monthly)')
    
    args = parser.parse_args()
    
    gcs = GCSBackup()
    
    if args.list:
        prefix = f"backups/{args.folder}/" if args.folder else "backups/"
        backups = gcs.list_backups(prefix)
        print(f"\n=== GCS Backups ({args.folder or 'all'}) ===")
        for backup in backups:
            print(f"  {backup['name']} - {backup['size']:.2f} MB - {backup.get('storage_class', 'STANDARD')}")
        if not backups:
            print("  No backups found")
        print()
    
    elif args.upload:
        count = gcs.upload_latest_backups(args.folder)
        folder_path = f"GCS/{args.folder}" if args.folder else "GCS"
        print(f"Uploaded {count} backup(s) to {folder_path}")
    
    elif args.restore:
        # Download to /api/backups directory
        local_path = gcs.backup_dir / args.restore
        if gcs.download_file(args.restore, local_path):
            print(f"Downloaded to {local_path}")
            print("Use restore.sh to restore from this file")
        else:
            print("Download failed")
    
    elif args.cleanup > 0:
        deleted = gcs.delete_old_backups(args.cleanup, args.folder)
        folder_path = f"{args.folder}/" if args.folder else ""
        print(f"Deleted {deleted} old backup(s) from backups/{folder_path}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
