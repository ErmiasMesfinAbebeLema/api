"""
Embedding service using Google Gemini for RAG functionality.
"""
import os
from typing import List, Dict, Any

# Configure Gemini
import google.generativeai as genai

# Gemini API key
GEMINI_API_KEY = "AIzaSyBEL_Ss8iZRaY54S94tAPsNZjf_9asnxyo"
genai.configure(api_key=GEMINI_API_KEY)

# Pinecone configuration
PINECONE_API_KEY = "pcsk_74AL3R_UVeDCgfZhLe1AsAU7ViExmNAc5HAXCSiXN2Zsqdr4VGiA4w624UdrVsDmWwy2kK"
PINECONE_ENVIRONMENT = "us-east1-gcp"

# Initialize Pinecone
try:
    from pinecone import Pinecone
    pc = Pinecone(api_key=PINECONE_API_KEY)
except Exception as e:
    print(f"Pinecone initialization error: {e}")
    pc = None

# Index name
INDEX_NAME = "faq-index"


def get_embedding(text: str) -> List[float]:
    """Get embedding for text using Gemini embedding model."""
    try:
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text,
            task_type="retrieval_document"
        )
        return result["embedding"]
    except Exception as e:
        print(f"Embedding error: {e}")
        return []


def initialize_index():
    """Initialize or connect to Pinecone index."""
    try:
        if pc is None:
            return None
        
        # Check if index exists
        existing_indexes = pc.list_indexes()
        if INDEX_NAME not in [idx.name for idx in existing_indexes]:
            # Create index if it doesn't exist - try AWS us-east-1
            pc.create_index(
                name=INDEX_NAME,
                dimension=3072,  # Gemini embedding dimension (gemini-embedding-001)
                spec={
                    "serverless": {
                        "cloud": "aws",
                        "region": "us-east-1"
                    }
                }
            )
        
        return pc.Index(INDEX_NAME)
    except Exception as e:
        print(f"Index initialization error: {e}")
        return None


def index_faqs(faqs: List[Dict[str, str]]):
    """Index FAQ data into Pinecone - only if index exists."""
    index = initialize_index()
    if index is None:
        print("Index not available - skipping FAQ indexing")
        return
    
    vectors = []
    for i, faq in enumerate(faqs):
        embedding = get_embedding(faq["question"])
        if embedding:
            vectors.append({
                "id": str(i),
                "values": embedding,
                "metadata": {
                    "question": faq["question"],
                    "answer": faq["answer"]
                }
            })
    
    if vectors:
        try:
            index.upsert(vectors=vectors)
            print(f"Indexed {len(vectors)} FAQs")
        except Exception as e:
            print(f"Index upsert error: {e}")


def retrieve_relevant_faqs(question: str, top_k: int = 3) -> List[Dict[str, str]]:
    """Retrieve relevant FAQs based on user question."""
    index = initialize_index()
    if index is None:
        return []
    
    try:
        query_embedding = get_embedding(question)
        if not query_embedding:
            return []
        
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True
        )
        
        relevant_faqs = []
        for match in results.get("matches", []):
            metadata = match.get("metadata", {})
            relevant_faqs.append({
                "question": metadata.get("question", ""),
                "answer": metadata.get("answer", "")
            })
        
        return relevant_faqs
    except Exception as e:
        print(f"Retrieval error: {e}")
        return []


# Full Academy FAQ data with correct location and contact info
ACADEMY_FAQS = [
    # Contact Information (from footer)
    {"question": "Where is YM International Beauty Academy located?", "answer": "We are located in Shashemene, Oromia Region, Ethiopia - specifically in the Abosto Area."},
    {"question": "What is your phone number?", "answer": "Our phone numbers are: +251 912 667 152, +251 954 811 648, +251 916 822 446, +251 916 858 323"},
    {"question": "What is your email address?", "answer": "Our main email is info@ymbeautyacademy.com. For admissions: info@ymbeautyacademy.com, Registrar: registrar@ymbeautyacademy.com, Student Affairs: students@ymbeautyacademy.com"},
    {"question": "What are your office hours?", "answer": "We are open Monday through Saturday from 8 AM to 6 PM."},
    
    # About the Institute
    {"question": "What is YM International Beauty Academy?", "answer": "YM International Beauty Academy is a professional beauty and wellness training institution located in Shashemene, Oromia Region, Ethiopia. Founded in 2014, we offer comprehensive programs in cosmetology, barbering, nail technology, and makeup artistry. Our mission is to provide quality beauty education that is accessible, practical, and empowering."},
    {"question": "What programs do you offer?", "answer": "We offer four main programs: Cosmetology (12 months) - Full spectrum of beauty services (hair, skin, nails), Barbering (9 months) - Precision cuts, shaves, fades, modern styling, Nail Technology (6 months) - Nail care, nail art, gel and acrylic applications, Makeup Artistry (6 months) - Everyday looks, editorial and bridal artistry."},
    {"question": "What is the duration of your courses?", "answer": "Course durations vary: Cosmetology: 12 months, Barbering: 9 months, Nail Technology: 6 months, Makeup Artistry: 6 months."},
    {"question": "What are the course levels?", "answer": "Our courses are designed for various skill levels: Beginner, Intermediate, and Advanced."},
    {"question": "What are your key statistics?", "answer": "We have: 32+ Years of Excellence, 20,000+ Graduates, 4 Programs, 90% Job Placement Rate."},
    
    # Admissions & Enrollment
    {"question": "How do I enroll in a course?", "answer": "To enroll: 1. Visit our website at https://yminternationalbeautyacademy.com 2. Navigate to the Courses page to view available programs 3. Click Apply Now or go to Registration 4. Create an account and fill in your details 5. Our admin team will contact you to complete the enrollment process."},
    {"question": "What information do I need to register?", "answer": "You will need: Full Name, Email address, Phone number, Date of Birth, Gender, Address information."},
    {"question": "What documents are required for enrollment?", "answer": "Required documents include: National ID or Passport, Previous educational certificates (Grade 8, 10, or 12), Profile photo, Contract (provided by institute)."},
    {"question": "Is there an enrollment fee?", "answer": "Enrollment fees vary by course. Our admin team will provide detailed pricing when you apply."},
    
    # Payments & Fees
    {"question": "How do I pay for my course?", "answer": "We accept multiple payment methods: Cash, Bank Transfer, Mobile Money, Credit Card, Check."},
    {"question": "Can I pay in installments?", "answer": "Yes, we offer payment plans. Contact our admin team to discuss installment options."},
    {"question": "How do I view my invoices?", "answer": "Log into your student portal and navigate to My Payments to view all invoices and payment history."},
    {"question": "How do I get a receipt for my payment?", "answer": "Payments are recorded in the system with transaction references. You can view payment history in your student portal."},
    
    # Certificates & Verification
    {"question": "How do I get a certificate after completing my course?", "answer": "After completing your course: 1. Your enrollment status will be updated to Completed by an admin 2. The admin will issue your certificate 3. You can download the PDF from your student portal."},
    {"question": "What is the certificate number format?", "answer": "Certificates follow the format: CERT-{YEAR}-{RANDOM_6_DIGITS}. Example: CERT-2026-114340"},
    {"question": "How do I verify a certificate?", "answer": "Go to the Certificate Verification page on our website and enter either: Certificate number, or Student ID."},
    {"question": "Can my certificate be revoked?", "answer": "Yes, certificates can be revoked for issues like fraud or academic misconduct. Revoked certificates show as Revoked when verified."},
    
    # Student Portal
    {"question": "How do I access the student portal?", "answer": "Log in at https://yminternationalbeautyacademy.com/login with your registered email and password."},
    {"question": "What can I do in the student portal?", "answer": "As a student, you can: View your profile and personal information, See your enrolled courses, View your certificates, Check payment history and invoices, View your attendance records, Request attendance for scheduled sessions, View available schedules, Update your profile photo."},
    {"question": "How do I update my profile information?", "answer": "Go to Profile in the student portal to update your personal details and upload a profile photo."},
    {"question": "How do I view my grades?", "answer": "Navigate to My Courses in the student portal to see your course progress and grades."},
    {"question": "How do I request attendance?", "answer": "In the student portal, go to the Attendance section to view available schedules and request attendance for scheduled sessions."},
    
    # Attendance
    {"question": "How does the attendance system work?", "answer": "Students can request attendance for scheduled sessions. Instructors then approve or reject these requests. You can also view your attendance history in the student portal."},
    {"question": "What happens if I don't request attendance?", "answer": "If you don't request attendance for a scheduled session, you may be marked as absent automatically by the system."},
    {"question": "What are the attendance statuses?", "answer": "Attendance can have these statuses: Pending (awaiting instructor approval), Approved, Rejected, Absent."},
    
    # Technical Support
    {"question": "I can't log in. What should I do?", "answer": "Try these steps: 1. Check your email and password are correct 2. Clear your browser cache 3. Use the Forgot Password feature to reset your password 4. Contact admin if the problem persists."},
    {"question": "How do I reset my password?", "answer": "Use the Forgot Password link on the login page. You'll receive an email to reset your password."},
    {"question": "What browsers are supported?", "answer": "We recommend using modern browsers like Chrome, Firefox, Safari, or Edge."},
    {"question": "Who do I contact for technical issues?", "answer": "Use the Contact page on our website to send us a message, or contact our admin team directly."},
    
    # General Inquiries
    {"question": "How do I contact the institute?", "answer": "Visit our Contact page at https://yminternationalbeautyacademy.com/contact to send us a message, or call us at +251 912 667 152."},
    {"question": "Can I visit the institute in person?", "answer": "Yes, you can visit us at Abosto Area, Shashemene, Oromia Region, Ethiopia. We're open Monday through Saturday, 8 AM to 6 PM."},
    {"question": "Do you offer online courses?", "answer": "Our courses are conducted in-person at our training facility in Shashemene."},
    {"question": "Are the courses accredited?", "answer": "Our institute provides professional training. Certificates are verifiable through our verification system."},
    {"question": "What makes YM International Beauty Academy different?", "answer": "We offer: Hands-On Training in fully equipped modern salons and labs, Industry Certified programs meeting national beauty industry standards, Career Placement services connecting graduates with top employers, Expert Instructors with years of industry experience, Flexible Schedules (full-time and part-time options), Small Class Sizes for personalized attention."},
    
    # User Roles
    {"question": "What user roles do you have?", "answer": "We have four roles: Super Admin (Full system access + permission management), Admin (Full access to all features), Instructor (Limited to assigned courses and student progress), Student (View own profile, courses, certificates, attendance)."},
    {"question": "What can a Super Admin do?", "answer": "Super Admin has full system access including: CRUD operations on all features, Permission management, Managing other admins, Assigning instructors to courses."},
    {"question": "What can an Admin do?", "answer": "Admin has full access to all features including: Students, Courses, Enrollments, Certificates, Payments, Invoices, Documents, Attendance, Reports."},
    {"question": "What can an Instructor do?", "answer": "Instructor has limited access: View assigned courses, Manage student progress for assigned courses, Approve/reject attendance requests for assigned courses, Issue certificates for assigned courses."},
    {"question": "What can a Student do?", "answer": "Student can: View own profile and courses, View own certificates, View own payment history, View and request own attendance, Update own profile photo."},
    
    # Admin Features
    {"question": "How do I add a new student?", "answer": "In the admin dashboard: 1. Navigate to Students 2. Click Add Student 3. Fill in all required fields 4. Click Save"},
    {"question": "How do I record attendance?", "answer": "In the admin dashboard: 1. Navigate to Attendance 2. View pending attendance requests 3. Approve or reject individual requests 4. Use bulk operations to approve/reject multiple at once"},
    {"question": "How do I create an invoice?", "answer": "In the admin dashboard: 1. Navigate to Invoices 2. Click New Invoice 3. Select student and add line items 4. Set due date and save"},
    {"question": "How do I record a payment?", "answer": "In the admin dashboard: 1. Navigate to Payments 2. Click Record Payment 3. Select student, enter amount and payment method 4. Enter transaction reference 5. Save"},
    {"question": "How do I issue a certificate?", "answer": "In the admin dashboard: 1. Navigate to Certificates 2. Click Issue Certificate 3. Select student and course 4. Choose template 5. Set dates and issue"},
    {"question": "How do I assign an instructor to a course?", "answer": "Only Super Admin can assign instructors: 1. Navigate to Instructor Courses 2. Click to create new assignment 3. Select instructor and course 4. Save"},
    {"question": "How do I manage admin permissions?", "answer": "Only Super Admin can manage permissions: 1. Navigate to Permissions 2. View all admin permissions 3. Create, update, or delete permissions for admins"},
    {"question": "What is the workflow for student enrollment?", "answer": "The workflow is: Add Student → Upload Documents → Create Enrollment → Create Invoice → Record Payment → Start Course → Complete Course → Issue Certificate"},
    
    # Statuses
    {"question": "What student statuses exist?", "answer": "Student statuses: Pending (Awaiting approval), Active (Currently enrolled), Graduated (Completed program), Suspended (Temporarily suspended), Withdrawn (Left program)."},
    {"question": "What enrollment statuses exist?", "answer": "Enrollment statuses: Pending, Active, Completed, Dropped."},
    {"question": "What certificate statuses are there?", "answer": "Certificate statuses: Active (Valid certificate), Revoked (Cancelled certificate), Expired (Past expiry date)."},
    {"question": "What invoice statuses exist?", "answer": "Invoice statuses: Draft, Sent, Paid, Completed, Cancelled."},
    {"question": "What payment statuses are there?", "answer": "Payment statuses: Pending, Completed, Refunded, Failed."},
    {"question": "What payment methods do you accept?", "answer": "We accept: Cash, Bank Transfer, Mobile Money, Credit Card, Check."},
    {"question": "What document types are required?", "answer": "Document types: National ID, Passport, Contract, Profile Photo, Grade 8 Certificate, Grade 10 Certificate, Grade 12 Certificate, Ethiopian Higher Education Entrance Exam."},
    {"question": "What reports are available?", "answer": "Available reports: Revenue Report (Revenue over time with filtering), Payments by Method (Payment breakdown by payment method), Payments by Course (Revenue breakdown by course), Dashboard Summary (Overview statistics), Attendance Report (Attendance statistics)."},
]