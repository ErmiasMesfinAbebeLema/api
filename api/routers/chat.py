import os
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.auth import get_current_active_user
from api.models import User
from api.services.embedding import retrieve_relevant_faqs, ACADEMY_FAQS, index_faqs


# Chat router
router = APIRouter(prefix="/chat", tags=["chat"])

# Groq API key - loaded from environment variable
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("Warning: GROQ_API_KEY not set in environment variables")

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-instruct")


# Request/Response schemas
class ChatAskRequest(BaseModel):
    question: str


class ChatAskResponse(BaseModel):
    answer: str
    thread_id: str | None = None


# In-memory chat history (session-based, per user)
chat_histories: dict[int, list[dict]] = {}

# Full Knowledge Base with correct location (Shashemene, Oromia Region)
KNOWLEDGE_BASE = """You are ሚኪ (Miki), an AI assistant for YM International Beauty Academy.

ABOUT THE INSTITUTE:
- Name: YM International Beauty Academy (Former Name: Mulat Beauty Training Institute)
- Founded: 2014
- Website: https://yminternationalbeautyacademy.com
- Location: Abosto Area, Shashemene, Oromia Region, Ethiopia
- Phone: +251 912 667 152, +251 954 811 648, +251 916 822 446, +251 916 858 323
- Email: info@ymbeautyacademy.com
- Office Hours: Mon – Sat: 8 AM – 6 PM
- 32+ Years of Excellence, 20,000+ Graduates, 90% Job Placement Rate

PROGRAMS OFFERED:
- Cosmetology (12 months) - Full spectrum of beauty services (hair, skin, nails)
- Barbering (9 months) - Precision cuts, shaves, fades, modern styling
- Nail Technology (6 months) - Nail care, nail art, gel and acrylic applications
- Makeup Artistry (6 months) - Everyday looks, editorial and bridal artistry

USER ROLES & PERMISSIONS:
- Super Admin: Full system access + permission management (CRUD on all, manage admins, assign instructors)
- Admin: Full access to all features (CRUD on students, courses, enrollments, certificates, payments, invoices, documents, attendance, reports)
- Instructor: Limited to assigned courses (view/edit assigned courses, manage student progress, approve/reject attendance, issue certificates)
- Student: View own profile, courses, certificates, payment history, attendance

FEATURES:
- Student Management: Add, edit, delete students
- Course Management: Create and manage courses
- Enrollment: Enroll students in courses
- Certificate Management: Issue and verify certificates (format: CERT-{YEAR}-{RANDOM_6_DIGITS})
- Payment & Invoice: Create invoices (format: INV-{YEAR}-{RANDOM_6_DIGITS}), record payments
- Document Management: Upload and manage student documents (National ID, Passport, Contract, Profile Photo, Grade certificates)
- Attendance: Track student attendance (Pending, Approved, Rejected, Absent)
- Reports: Revenue, payment, attendance reports

STATUSES:
- Student Statuses: Pending, Active, Graduated, Suspended, Withdrawn
- Enrollment Statuses: Pending, Active, Completed, Dropped
- Certificate Statuses: Active, Revoked, Expired
- Invoice Statuses: Draft, Sent, Paid, Completed, Cancelled
- Payment Statuses: Pending, Completed, Refunded, Failed

PAYMENT METHODS: Cash, Bank Transfer, Mobile Money, Credit Card, Check

OFFICES:
- Admissions: info@ymbeautyacademy.com
- Registrar: registrar@ymbeautyacademy.com
- Student Affairs: students@ymbeautyacademy.com

ENROLLMENT WORKFLOW:
Add Student → Upload Documents → Create Enrollment → Create Invoice → Record Payment → Start Course → Complete Course → Issue Certificate

STUDENT PORTAL: Login at /login to view courses, certificates, payments, attendance, update profile

CERTIFICATE VERIFICATION: Use /verify page with certificate number or student ID

RESPONSE STYLE:
- Be helpful, friendly, and professional
- Provide accurate information based on the knowledge base
- Keep responses concise and well-structured
- Use bullet points or numbered lists for multiple items
- Use clear paragraph breaks between different topics
- If you don't know something, say so and suggest contacting admin at info@ymbeautyacademy.com or call +251 912 667 152
"""

# Initialize index on module load
_indexed = False


def ensure_indexed():
    """Ensure FAQs are indexed on first use."""
    global _indexed
    if not _indexed:
        try:
            index_faqs(ACADEMY_FAQS)
            _indexed = True
        except Exception as e:
            print(f"Index initialization: {e}")


# Lazy-loaded Groq client
_client = None


def get_client():
    """Get or create Groq client (lazy initialization)"""
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Groq API key not configured. Please set GROQ_API_KEY environment variable."
            )
        from groq import Groq
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


@router.post("/ask", response_model=ChatAskResponse)
async def ask_chat(
    request: ChatAskRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Ask the AI assistant a question.
    Requires authentication.
    Uses RAG (Pinecone + Gemini) for knowledge retrieval + Groq for response.
    """
    if not request.question or not request.question.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question cannot be empty"
        )

    try:
        # Ensure FAQs are indexed
        ensure_indexed()
        
        client = get_client()
        
        # Get user's chat history
        user_id = current_user.id
        if user_id not in chat_histories:
            chat_histories[user_id] = []
        
        history = chat_histories[user_id]
        
        # Retrieve relevant FAQs using RAG from Pinecone
        relevant_faqs = retrieve_relevant_faqs(request.question, top_k=5)
        
        # Build context from retrieved FAQs
        context = ""
        if relevant_faqs:
            context = "\n\nRelevant Information from Knowledge Base:\n"
            for faq in relevant_faqs:
                context += f"Q: {faq['question']}\nA: {faq['answer']}\n\n"
        
        # Build system prompt with RAG context
        system_prompt = KNOWLEDGE_BASE
        if context:
            system_prompt += f"\n{context}"
        
        # Build messages for chat completion
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history (limit to last 10 messages to keep context)
        recent_history = history[-10:] if len(history) > 10 else history
        for msg in recent_history:
            messages.append(msg)
        
        # Add current question
        messages.append({"role": "user", "content": request.question})
        
        # Call Groq API
        chat_completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )
        
        # Extract the answer
        answer = chat_completion.choices[0].message.content if chat_completion.choices else "I apologize, but I couldn't generate a response."
        
        if not answer:
            answer = "I apologize, but I couldn't generate a response."
        
        # Add to chat history
        chat_histories[user_id].append({"role": "user", "content": request.question})
        chat_histories[user_id].append({"role": "assistant", "content": answer})
        
        # Limit history to last 20 messages to prevent memory issues
        if len(chat_histories[user_id]) > 20:
            chat_histories[user_id] = chat_histories[user_id][-20:]
        
        return ChatAskResponse(answer=answer, thread_id=None)

    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Chat error: {str(e)}")
        
        return ChatAskResponse(
            answer="I apologize, but I'm having trouble connecting right now. Please try again later.",
            thread_id=None
        )


@router.post("/clear")
async def clear_chat(
    current_user: User = Depends(get_current_active_user)
):
    """Clear the user's chat history"""
    user_id = current_user.id
    if user_id in chat_histories:
        chat_histories[user_id] = []
    return {"message": "Chat history cleared"}


@router.get("/history")
async def get_chat_history(
    current_user: User = Depends(get_current_active_user)
):
    """Get the user's chat history"""
    user_id = current_user.id
    return {"messages": chat_histories.get(user_id, [])}
