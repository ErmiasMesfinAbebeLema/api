-- SQL commands to fix the userrole enum to use uppercase values
-- Run these in PostgreSQL (psql or pgweb)

-- Step 1: Add uppercase values to the enum
ALTER TYPE userrole ADD VALUE 'ADMIN';
ALTER TYPE userrole ADD VALUE 'INSTRUCTOR';
ALTER TYPE userrole ADD VALUE 'STUDENT';
ALTER TYPE userrole ADD VALUE 'SUPER_ADMIN';

-- Step 2: Update all existing users to use uppercase values
UPDATE users SET role = 'ADMIN'::userrole WHERE role = 'admin'::userrole;
UPDATE users SET role = 'INSTRUCTOR'::userrole WHERE role = 'instructor'::userrole;
UPDATE users SET role = 'STUDENT'::userrole WHERE role = 'student'::userrole;
UPDATE users SET role = 'SUPER_ADMIN'::userrole WHERE role = 'super_admin'::userrole;

-- Step 3: Verify the current users table
SELECT id, email, full_name, role FROM users;

-- Step 4: Check current enum values (both old and new will exist)
SELECT enumlabel FROM pg_enum 
WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole') 
ORDER BY enumsortorder;
