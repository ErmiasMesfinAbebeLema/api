from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from api.models import Notification, Enrollment, Invoice, Payment, User, UserRole, Student


class NotificationService:
    """Async Service for creating automatic notifications"""
    
    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        link: str = None,
        created_by: int = None
    ) -> Notification:
        """Create a single notification"""
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            link=link,
            created_by=created_by
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification
    
    @staticmethod
    async def notify_enrollment_completion(
        db: AsyncSession,
        enrollment_id: int,
        created_by: int = None
    ):
        """Notify when a student completes an enrollment/course"""
        result = await db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))
        enrollment = result.scalar_one_or_none()
        if not enrollment:
            return None
        
        # Notify student
        if enrollment.student and enrollment.student.user:
            student_user = enrollment.student.user
            await NotificationService.create_notification(
                db=db,
                user_id=student_user.id,
                notification_type="enrollment",
                title="🎉 Course Completed!",
                message=f"Great job! You've successfully completed {enrollment.course.name if enrollment.course else 'your course'}. Your hard work has paid off!",
                link=f"/student/courses",
                created_by=created_by
            )
        
        return enrollment
    
    @staticmethod
    async def notify_enrollment_created(
        db: AsyncSession,
        enrollment_id: int,
        created_by: int = None
    ):
        """Notify when a new enrollment is created"""
        result = await db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))
        enrollment = result.scalar_one_or_none()
        if not enrollment:
            return None
        
        # Notify student
        if enrollment.student and enrollment.student.user:
            student_user = enrollment.student.user
            course_name = enrollment.course.name if enrollment.course else "a course"
            await NotificationService.create_notification(
                db=db,
                user_id=student_user.id,
                notification_type="enrollment",
                title="✅ You're Enrolled!",
                message=f"You have enrolled in '{course_name}'. Welcome aboard!",
                link=f"/student/courses",
                created_by=created_by
            )
        
        # Notify admins - create only ONE notification for admin team
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        if admins and enrollment.student and enrollment.student.user:
            student_name = enrollment.student.user.full_name or "Unknown"
            course_name = enrollment.course.name if enrollment.course else "a course"
            # Create ONE notification for admin team (broadcast)
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="📝 New Enrollment",
                message=f"{student_name} has enrolled in '{course_name}'.",
                link=f"/admin/enrollments",
                created_by=created_by
            )
        
        return enrollment
    
    @staticmethod
    async def notify_payment_received(
        db: AsyncSession,
        payment_id: int,
        created_by: int = None
    ):
        """Notify when a payment is received"""
        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()
        if not payment:
            return None
        
        # Notify student
        if payment.enrollment and payment.enrollment.student and payment.enrollment.student.user:
            student_user = payment.enrollment.student.user
            course_name = payment.enrollment.course.name if payment.enrollment.course else "the course"
            await NotificationService.create_notification(
                db=db,
                user_id=student_user.id,
                notification_type="payment",
                title="💰 Payment Received",
                message=f"Your payment of {payment.amount} for '{course_name}' has been received.",
                link=f"/student/payments",
                created_by=created_by
            )
        
        # Notify admins - create only ONE notification for admin team
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        if admins and payment.enrollment and payment.enrollment.student and payment.enrollment.student.user:
            student_name = payment.enrollment.student.user.full_name or "Unknown"
            course_name = payment.enrollment.course.name if payment.enrollment and payment.enrollment.course else "a course"
            # Create ONE notification for admin team (broadcast)
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="💵 Payment Received",
                message=f"{student_name} has made a payment of {payment.amount} for '{course_name}'.",
                link=f"/admin/payments",
                created_by=created_by
            )
        
        return payment
    
    @staticmethod
    async def notify_certificate_issued(
        db: AsyncSession,
        certificate_id: int,
        created_by: int = None
    ):
        """Notify when a certificate is issued"""
        from api.models import Certificate
        result = await db.execute(select(Certificate).where(Certificate.id == certificate_id))
        certificate = result.scalar_one_or_none()
        if not certificate:
            return None
        
        # Notify student
        if certificate.student and certificate.student.user:
            student_user = certificate.student.user
            course_name = certificate.course.name if certificate.course else "the course"
            await NotificationService.create_notification(
                db=db,
                user_id=student_user.id,
                notification_type="certificate",
                title="🏆 Certificate Ready!",
                message=f"Your certificate for '{course_name}' is now available.",
                link=f"/student/certificates",
                created_by=created_by
            )
        
        return certificate
    
    @staticmethod
    async def notify_unpaid_invoices(db: AsyncSession, created_by: int = None):
        """Check and notify admins about unpaid invoices"""
        # Get invoices that are overdue (more than 30 days old and not paid)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        result = await db.execute(
            select(Invoice).where(
                Invoice.status != "PAID",
                Invoice.due_date < thirty_days_ago
            )
        )
        overdue_invoices = result.scalars().all()
        
        if not overdue_invoices:
            return []
        
        # Get admins
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        # Create only ONE notification for admin team (broadcast)
        if admins:
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="⚠️ Overdue Payments",
                message=f"There are {len(overdue_invoices)} overdue invoice(s) waiting for payment. Let's follow up with the students!",
                link=f"/admin/invoices?status=overdue",
                created_by=created_by
            )
        
        return []
    
    @staticmethod
    async def notify_enrollment_expiring(db: AsyncSession, created_by: int = None):
        """Check and notify about enrollments nearing completion (within 30 days)"""
        thirty_days_from_now = datetime.utcnow() + timedelta(days=30)
        
        # Find active enrollments that will expire within 30 days
        result = await db.execute(
            select(Enrollment).where(
                Enrollment.status == "active",
                Enrollment.completion_date <= thirty_days_from_now,
                Enrollment.completion_date >= datetime.utcnow()
            )
        )
        expiring_enrollments = result.scalars().all()
        
        if not expiring_enrollments:
            return []
        
        # Get admins
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        # Create only ONE notification for admin team (broadcast)
        if admins:
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="📅 Courses Ending Soon",
                message=f"{len(expiring_enrollments)} student(s) will finish their courses in the next 30 days. Time to prepare certificates!",
                link=f"/admin/enrollments?status=active",
                created_by=created_by
            )
        
        return []
    
    @staticmethod
    async def notify_completed_enrollments(db: AsyncSession, created_by: int = None):
        """Check and notify about recently completed enrollments"""
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        
        # Find enrollments that completed in the last day
        result = await db.execute(
            select(Enrollment).where(
                Enrollment.status == "completed",
                Enrollment.updated_at >= one_day_ago
            )
        )
        completed_enrollments = result.scalars().all()
        
        if not completed_enrollments:
            return []
        
        # Get admins
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        # Create only ONE notification for admin team (broadcast)
        if admins:
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="Enrollments Completed",
                message=f"{len(completed_enrollments)} enrollment(s) were completed in the last 24 hours.",
                link=f"/admin/enrollments?status=completed",
                created_by=created_by
            )
        
        return []
    
    @staticmethod
    async def notify_enrollment_updated(
        db: AsyncSession,
        enrollment_id: int,
        old_status: str,
        new_status: str,
        created_by: int = None
    ):
        """Notify when an enrollment status is updated"""
        result = await db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))
        enrollment = result.scalar_one_or_none()
        if not enrollment:
            return None
        
        # Notify student about status change
        if enrollment.student and enrollment.student.user:
            student_user = enrollment.student.user
            course_name = enrollment.course.name if enrollment.course else "the course"
            
            # Different messages based on status
            if new_status == "active":
                title = "🚀 Enrollment Activated"
                message = f"Your enrollment in '{course_name}' is now active."
                link = f"/student/courses"
            elif new_status == "suspended":
                title = "⏸️ Enrollment Suspended"
                message = f"Your enrollment in '{course_name}' has been suspended."
                link = f"/student/courses"
            elif new_status == "cancelled":
                title = "❌ Enrollment Cancelled"
                message = f"Your enrollment in '{course_name}' has been cancelled."
                link = f"/student/courses"
            elif new_status == "completed":
                title = "🎉 Course Completed!"
                message = f"Congratulations! You have completed '{course_name}'."
                link = f"/student/courses"
            else:
                title = "📋 Enrollment Updated"
                message = f"Your enrollment status in '{course_name}' has been updated to '{new_status}'."
                link = f"/student/courses"
            
            await NotificationService.create_notification(
                db=db,
                user_id=student_user.id,
                notification_type="enrollment",
                title=title,
                message=message,
                link=link,
                created_by=created_by
            )
        
        # Notify admins about status change - create only ONE notification for admin team
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        if admins and enrollment.student and enrollment.student.user:
            student_name = enrollment.student.user.full_name or "Unknown"
            course_name = enrollment.course.name if enrollment.course else "a course"
            # Create ONE notification for admin team (broadcast)
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="📋 Enrollment Updated",
                message=f"{student_name}'s enrollment in '{course_name}' status has been updated to '{new_status}'.",
                link=f"/admin/enrollments",
                created_by=created_by
            )
        
        return enrollment
    
    @staticmethod
    async def notify_invoice_created(
        db: AsyncSession,
        invoice_id: int,
        created_by: int = None
    ):
        """Notify when a new invoice is created"""
        result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
        invoice = result.scalar_one_or_none()
        if not invoice:
            return None
        
        # Notify student
        if invoice.student and invoice.student.user:
            student_user = invoice.student.user
            await NotificationService.create_notification(
                db=db,
                user_id=student_user.id,
                notification_type="payment",
                title="📄 New Invoice",
                message=f"You have received invoice ({invoice.invoice_number}) for {invoice.grand_total}.",
                link=f"/student/invoices",
                created_by=created_by
            )
        
        return invoice
    
    @staticmethod
    async def notify_invoice_sent(
        db: AsyncSession,
        invoice_id: int,
        created_by: int = None
    ):
        """Notify when an invoice is sent to student via email"""
        result = await db.execute(select(Invoice).options(selectinload(Invoice.student).selectinload(Student.user)).where(Invoice.id == invoice_id))
        invoice = result.scalar_one_or_none()
        if not invoice:
            return None
        
        # Get student name
        student_name = invoice.student.user.full_name if invoice.student and invoice.student.user else "Unknown"
        
        # Notify admins
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        if admins:
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="📧 Invoice Sent",
                message=f"Invoice ({invoice.invoice_number}) for {invoice.grand_total} has been sent to {student_name}.",
                link=f"/admin/invoices",
                created_by=created_by
            )
        
        # Notify student
        if invoice.student and invoice.student.user:
            await NotificationService.create_notification(
                db=db,
                user_id=invoice.student.user.id,
                notification_type="payment",
                title="📧 Invoice Sent",
                message=f"Invoice ({invoice.invoice_number}) for {invoice.grand_total} has been sent to your email.",
                link=f"/student/invoices",
                created_by=created_by
            )
        
        return invoice
    
    @staticmethod
    async def notify_invoice_updated(
        db: AsyncSession,
        invoice_id: int,
        old_status: str,
        new_status: str,
        created_by: int = None
    ):
        """Notify when an invoice status is updated"""
        result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
        invoice = result.scalar_one_or_none()
        if not invoice:
            return None
        
        # Notify student about status change
        if invoice.student and invoice.student.user:
            student_user = invoice.student.user
            
            if new_status == "PAID" or new_status == "COMPLETED":
                title = "✅ Invoice Paid"
                message = f"Your invoice ({invoice.invoice_number}) for {invoice.grand_total} has been paid."
                link = f"/student/invoices"
            elif new_status == "OVERDUE":
                title = "⏰ Invoice Overdue"
                message = f"Your invoice ({invoice.invoice_number}) for {invoice.grand_total} is now overdue."
                link = f"/student/invoices"
            elif new_status == "CANCELLED":
                title = "❌ Invoice Cancelled"
                message = f"Your invoice ({invoice.invoice_number}) has been cancelled."
                link = f"/student/invoices"
            else:
                title = "📋 Invoice Updated"
                message = f"Your invoice ({invoice.invoice_number}) status has been updated to '{new_status}'."
                link = f"/student/invoices"
            
            await NotificationService.create_notification(
                db=db,
                user_id=student_user.id,
                notification_type="payment",
                title=title,
                message=message,
                link=link,
                created_by=created_by
            )
        
        return invoice
    
    @staticmethod
    async def notify_payment_updated(
        db: AsyncSession,
        payment_id: int,
        old_status: str,
        new_status: str,
        created_by: int = None
    ):
        """Notify when a payment status is updated"""
        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()
        if not payment:
            return None
        
        # Notify student about status change
        if payment.enrollment and payment.enrollment.student and payment.enrollment.student.user:
            student_user = payment.enrollment.student.user
            course_name = payment.enrollment.course.name if payment.enrollment.course else "the course"
            
            if new_status == "COMPLETED":
                title = "✅ Payment Confirmed"
                message = f"Your payment of {payment.amount} for '{course_name}' has been confirmed."
                link = f"/student/payments"
            elif new_status == "FAILED":
                title = "❌ Payment Failed"
                message = f"Your payment of {payment.amount} for '{course_name}' has failed."
                link = f"/student/payments"
            elif new_status == "REFUNDED":
                title = "💰 Payment Refunded"
                message = f"Your payment of {payment.amount} for '{course_name}' has been refunded."
                link = f"/student/payments"
            else:
                title = "💳 Payment Updated"
                message = f"Your payment of {payment.amount} status has been updated to '{new_status}'."
                link = f"/student/payments"
            
            await NotificationService.create_notification(
                db=db,
                user_id=student_user.id,
                notification_type="payment",
                title=title,
                message=message,
                link=link,
                created_by=created_by
            )
        
        return payment
    
    @staticmethod
    async def notify_certificate_updated(
        db: AsyncSession,
        certificate_id: int,
        old_status: str,
        new_status: str,
        created_by: int = None
    ):
        """Notify when a certificate status is updated"""
        from api.models import Certificate
        result = await db.execute(select(Certificate).where(Certificate.id == certificate_id))
        certificate = result.scalar_one_or_none()
        if not certificate:
            return None
        
        # Notify student about status change
        if certificate.student and certificate.student.user:
            student_user = certificate.student.user
            course_name = certificate.course.name if certificate.course else "the course"
            
            if new_status == "REVOKED":
                title = "⚠️ Certificate Revoked"
                message = f"Your certificate for '{course_name}' has been revoked."
                link = f"/student/certificates"
            elif new_status == "EXPIRED":
                title = "⏳ Certificate Expired"
                message = f"Your certificate for '{course_name}' has expired."
                link = f"/student/certificates"
            elif new_status == "ACTIVE":
                title = "✅ Certificate Active"
                message = f"Your certificate for '{course_name}' is now verified and active."
                link = f"/student/certificates"
            else:
                title = "📜 Certificate Updated"
                message = f"Your certificate for '{course_name}' status has been updated to '{new_status}'."
                link = f"/student/certificates"
            
            await NotificationService.create_notification(
                db=db,
                user_id=student_user.id,
                notification_type="certificate",
                title=title,
                message=message,
                link=link,
                created_by=created_by
            )
        
        return certificate
    
    @staticmethod
    async def notify_student_created(
        db: AsyncSession,
        student_id: int,
        created_by: int = None
    ):
        """Notify when a new student is registered"""
        # Load student with user relationship
        result = await db.execute(
            select(Student).options(selectinload(Student.user)).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()
        if not student:
            return None
        
        student_name = student.user.full_name if student and student.user else "Unknown"
        
        # Notify the student
        if student.user:
            await NotificationService.create_notification(
                db=db,
                user_id=student.user.id,
                notification_type="student",
                title="🎉 Welcome to the Academy!",
                message="Your student account is ready! Browse our courses and start your learning journey today.",
                link=f"/courses",
                created_by=created_by
            )
        
        # Notify admins - create only ONE notification for all admins (broadcast)
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        if admins:
            # Create ONE notification to the first admin as a broadcast
            # The notification type indicates it's for admin team
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="👋 New Student Registered",
                message=f"{student_name} has registered as a new student.",
                link=f"/admin/students",
                created_by=created_by
            )
        
        return student
    
    @staticmethod
    async def notify_student_updated(
        db: AsyncSession,
        student_id: int,
        updated_fields: list,
        created_by: int = None
    ):
        """Notify when a student profile is updated"""
        # Load student with user relationship
        result = await db.execute(
            select(Student).options(selectinload(Student.user)).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()
        if not student:
            return None
        
        # Get student name for friendly message
        student_name = student.user.full_name if student and student.user else "Your profile"
        
        # Map technical field names to user-friendly labels and determine which to show
        important_fields = {
            "first_name": "First Name",
            "last_name": "Last Name", 
            "full_name": "Full Name",
            "phone": "Phone Number",
            "email": "Email Address",
            "emergency_contact_name": "Emergency Contact Name",
            "emergency_contact_phone": "Emergency Contact Phone",
            "address_line1": "Address",
            "city": "City",
            "enrollment_status": "Enrollment Status",
            "program_type": "Program Type"
        }
        
        # Show up to 3 important field changes with names, rest as count
        important_updates = []
        other_count = 0
        
        for field in updated_fields:
            if field in important_fields:
                important_updates.append(important_fields[field])
            else:
                other_count += 1
        
        # Create a meaningful message
        if len(updated_fields) == 1:
            message = f"{student_name} - Your {important_updates[0] if important_updates else updated_fields[0]} has been updated successfully."
        elif len(updated_fields) == 2:
            f1 = important_updates[0] if important_updates else updated_fields[0]
            f2 = important_updates[1] if len(important_updates) > 1 else updated_fields[1]
            message = f"{student_name} - Your {f1} and {f2} have been updated successfully."
        elif len(updated_fields) <= 4:
            shown = important_updates[:len(updated_fields)] if important_updates else updated_fields
            if len(shown) > 1:
                fields_str = ", ".join(shown[:-1]) + f" and {shown[-1]}"
            else:
                fields_str = shown[0]
            message = f"{student_name} - Your {fields_str} have been updated successfully."
        else:
            # Show first 3 important or any fields, then count of remaining
            shown = important_updates[:3] if important_updates else updated_fields[:3]
            remaining = len(updated_fields) - len(shown)
            if remaining > 0:
                fields_str = ", ".join(shown) + f" and {remaining} more"
            else:
                fields_str = ", ".join(shown)
            message = f"{student_name} - Your {fields_str} have been updated successfully."
        
        # Notify the student
        if student.user:
            await NotificationService.create_notification(
                db=db,
                user_id=student.user.id,
                notification_type="student",
                title="✅ Profile Updated",
                message=message,
                link=f"/student/profile",
                created_by=created_by
            )
        
        return student
    
    @staticmethod
    async def notify_instructor_enrollment(
        db: AsyncSession,
        enrollment_id: int,
        created_by: int = None
    ):
        """Notify instructors when a new student enrolls in their course"""
        from api.models import Enrollment, InstructorCourse
        
        result = await db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))
        enrollment = result.scalar_one_or_none()
        if not enrollment:
            return None
        
        # Find instructors for this course
        instructor_result = await db.execute(
            select(InstructorCourse).where(InstructorCourse.course_id == enrollment.course_id)
        )
        instructor_courses = instructor_result.scalars().all()
        
        if not instructor_courses:
            return enrollment
        
        student_name = enrollment.student.user.full_name if enrollment.student and enrollment.student.user else "Unknown"
        course_name = enrollment.course.name if enrollment.course else "the course"
        
        # Notify each instructor
        for ic in instructor_courses:
            if ic.instructor and ic.instructor.user:
                await NotificationService.create_notification(
                    db=db,
                    user_id=ic.instructor.user.id,
                    notification_type="instructor",
                    title="📚 New Student Enrolled",
                    message=f"{student_name} has enrolled in your course '{course_name}'.",
                    link=f"/instructor/students",
                    created_by=created_by
                )
        
        return enrollment
    
    @staticmethod
    async def notify_student_attendance(
        db: AsyncSession,
        attendance_id: int,
        created_by: int = None
    ):
        """Notify student about their attendance record"""
        from api.models import Attendance
        
        result = await db.execute(select(Attendance).where(Attendance.id == attendance_id))
        attendance = result.scalar_one_or_none()
        if not attendance:
            return None
        
        # Notify the student
        if attendance.student and attendance.student.user:
            student_user = attendance.student.user
            course_name = attendance.course.name if attendance.course else "the course"
            status_text = "present" if attendance.status.value == "present" else "absent"
            
            await NotificationService.create_notification(
                db=db,
                user_id=attendance.student.user.id,
                notification_type="attendance",
                title="📅 Attendance Recorded",
                message=f"Your attendance for '{course_name}' has been marked as {status_text}.",
                link=f"/student/attendance",
                created_by=created_by
            )
        
        return attendance
    
    @staticmethod
    async def notify_instructor_attendance(
        db: AsyncSession,
        attendance_id: int,
        created_by: int = None
    ):
        """Notify instructor about attendance record"""
        from api.models import Attendance, InstructorCourse
        
        result = await db.execute(select(Attendance).where(Attendance.id == attendance_id))
        attendance = result.scalar_one_or_none()
        if not attendance:
            return None
        
        # Find instructors for this course
        instructor_result = await db.execute(
            select(InstructorCourse).where(InstructorCourse.course_id == attendance.course_id)
        )
        instructor_courses = instructor_result.scalars().all()
        
        if not instructor_courses:
            return attendance
        
        student_name = attendance.student.user.full_name if attendance.student and attendance.student.user else "Unknown"
        course_name = attendance.course.name if attendance.course else "the course"
        status_text = "present" if attendance.status.value == "present" else "absent"
        
        # Notify each instructor
        for ic in instructor_courses:
            if ic.instructor and ic.instructor.user:
                await NotificationService.create_notification(
                    db=db,
                    user_id=ic.instructor.user.id,
                    notification_type="attendance",
                    title="📋 Attendance Recorded",
                    message=f"{student_name}'s attendance for '{course_name}' has been marked as {status_text}.",
                    link=f"/instructor/attendance",
                    created_by=created_by
                )
        
        return attendance
    
    # =============================================================================
    # COURSE NOTIFICATIONS
    # =============================================================================
    
    @staticmethod
    async def notify_course_created(
        db: AsyncSession,
        course_id: int,
        created_by: int = None
    ):
        """Notify when a new course is created"""
        from api.models import Course
        result = await db.execute(select(Course).where(Course.id == course_id))
        course = result.scalar_one_or_none()
        if not course:
            return None
        
        # Notify admins - create only ONE notification for admin team
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        if admins:
            # Create ONE notification for admin team (broadcast)
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="📚 New Course Created",
                message=f"A new course '{course.name}' has been created.",
                link=f"/admin/courses",
                created_by=created_by
            )
        
        return course
    
    @staticmethod
    async def notify_course_updated(
        db: AsyncSession,
        course_id: int,
        updated_fields: list,
        created_by: int = None
    ):
        """Notify when a course is updated"""
        from api.models import Course
        result = await db.execute(select(Course).where(Course.id == course_id))
        course = result.scalar_one_or_none()
        if not course:
            return None
        
        # Notify admins - create only ONE notification for admin team
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        fields_str = ", ".join(updated_fields) if updated_fields else "details"
        if admins:
            # Create ONE notification for admin team (broadcast)
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="✏️ Course Updated",
                message=f"Course '{course.name}' has been updated. Changes: {fields_str}.",
                link=f"/admin/courses",
                created_by=created_by
            )
        
        return course
    
    @staticmethod
    async def notify_course_deleted(
        db: AsyncSession,
        course_id: int,
        course_name: str,
        created_by: int = None
    ):
        """Notify when a course is deleted"""
        # Notify admins - create only ONE notification for admin team
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        if admins:
            # Create ONE notification for admin team (broadcast)
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="🗑️ Course Deleted",
                message=f"Course '{course_name}' has been deleted.",
                link=f"/admin/courses",
                created_by=created_by
            )
        
        return None
    
    # =============================================================================
    # DOCUMENT NOTIFICATIONS
    # =============================================================================
    
    @staticmethod
    async def notify_document_uploaded(
        db: AsyncSession,
        document_id: int,
        created_by: int = None
    ):
        """Notify when a document is uploaded"""
        from api.models import StudentDocument
        result = await db.execute(select(StudentDocument).options(selectinload(StudentDocument.student).selectinload(Student.user)).where(StudentDocument.id == document_id))
        document = result.scalar_one_or_none()
        if not document:
            return None
        
        student_name = document.student.user.full_name if document.student and document.student.user else "Unknown" if document.student and document.student.user else "Unknown"
        
        # Notify admins - create only ONE notification for admin team
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        if admins:
            # Create ONE notification for admin team (broadcast)
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="📎 Document Uploaded",
                message=f"{student_name} has uploaded a '{document.document_type}' document.",
                link=f"/admin/documents/{document.student_id}",
                created_by=created_by
            )
        
        # Notify student
        if document.student and document.student.user:
            await NotificationService.create_notification(
                db=db,
                user_id=document.student.user.id,
                notification_type="document",
                title="✅ Document Uploaded",
                message=f"Your '{document.document_type}' document has been uploaded successfully.",
                link=f"/student/documents",
                created_by=created_by
            )
        
        return document
    
    @staticmethod
    async def notify_document_updated(
        db: AsyncSession,
        document_id: int,
        created_by: int = None
    ):
        """Notify when a document is updated"""
        from api.models import StudentDocument
        result = await db.execute(select(StudentDocument).options(selectinload(StudentDocument.student).selectinload(Student.user)).where(StudentDocument.id == document_id))
        document = result.scalar_one_or_none()
        if not document:
            return None
        
        student_name = document.student.user.full_name if document.student and document.student.user else "Unknown" if document.student and document.student.user else "Unknown"
        
        # Notify admins - create only ONE notification for admin team
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        if admins:
            # Create ONE notification for admin team (broadcast)
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="✏️ Document Updated",
                message=f"{student_name}'s '{document.document_type}' document has been updated.",
                link=f"/admin/documents/{document.student_id}",
                created_by=created_by
            )
        
        return document
    
    @staticmethod
    async def notify_document_deleted(
        db: AsyncSession,
        student_id: int,
        document_type: str,
        student_name: str,
        created_by: int = None
    ):
        """Notify when a document is deleted"""
        # Notify admins - create only ONE notification for admin team
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        if admins:
            # Create ONE notification for admin team (broadcast)
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="🗑️ Document Deleted",
                message=f"{student_name}'s '{document_type}' document has been deleted.",
                link=f"/admin/documents/{student_id}",
                created_by=created_by
            )
        
        return None
    
    # =============================================================================
    # DELETE NOTIFICATIONS (for students)
    # =============================================================================
    
    @staticmethod
    async def notify_enrollment_deleted(
        db: AsyncSession,
        student_id: int,
        course_name: str,
        student_name: str,
        created_by: int = None
    ):
        """Notify when an enrollment is deleted"""
        # Notify student
        student_result = await db.execute(select(Student).where(Student.id == student_id))
        student = student_result.scalar_one_or_none()
        if student and student.user:
            await NotificationService.create_notification(
                db=db,
                user_id=student.user.id,
                notification_type="enrollment",
                title="❌ Enrollment Cancelled",
                message=f"Your enrollment in '{course_name}' has been cancelled.",
                link=f"/student/courses",
                created_by=created_by
            )
        
        # Notify admins - create only ONE notification for admin team
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        if admins:
            # Create ONE notification for admin team (broadcast)
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="🗑️ Enrollment Deleted",
                message=f"{student_name}'s enrollment in '{course_name}' has been deleted.",
                link=f"/admin/enrollments",
                created_by=created_by
            )
        
        return None
    
    @staticmethod
    async def notify_payment_deleted(
        db: AsyncSession,
        payment_id: int,
        payment_amount: float,
        student_name: str,
        course_name: str,
        created_by: int = None
    ):
        """Notify when a payment is deleted"""
        # Notify student
        from api.models import Payment
        result = await db.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()
        if payment and payment.enrollment and payment.enrollment.student and payment.enrollment.student.user:
            await NotificationService.create_notification(
                db=db,
                user_id=payment.enrollment.student.user.id,
                notification_type="payment",
                title="❌ Payment Deleted",
                message=f"Your payment of {payment_amount} for '{course_name}' has been deleted.",
                link=f"/student/payments",
                created_by=created_by
            )
        
        # Notify admins - create only ONE notification for admin team
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        if admins:
            # Create ONE notification for admin team (broadcast)
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="🗑️ Payment Deleted",
                message=f"{student_name}'s payment of {payment_amount} for '{course_name}' has been deleted.",
                link=f"/admin/payments",
                created_by=created_by
            )
        
        return payment
    
    @staticmethod
    async def notify_invoice_deleted(
        db: AsyncSession,
        invoice_id: int,
        invoice_number: str,
        student_name: str,
        created_by: int = None
    ):
        """Notify when an invoice is deleted"""
        # Notify student
        from api.models import Invoice
        result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
        invoice = result.scalar_one_or_none()
        if invoice and invoice.student and invoice.student.user:
            await NotificationService.create_notification(
                db=db,
                user_id=invoice.student.user.id,
                notification_type="payment",
                title="❌ Invoice Deleted",
                message=f"Invoice ({invoice_number}) has been deleted.",
                link=f"/student/invoices",
                created_by=created_by
            )
        
        # Notify admins - create only ONE notification for admin team
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        if admins:
            # Create ONE notification for admin team (broadcast)
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="🗑️ Invoice Deleted",
                message=f"{student_name}'s invoice ({invoice_number}) has been deleted.",
                link=f"/admin/invoices",
                created_by=created_by
            )
        
        return invoice
    
    @staticmethod
    async def notify_student_deleted(
        db: AsyncSession,
        student_id: int,
        student_name: str,
        created_by: int = None
    ):
        """Notify when a student is deleted"""
        # Notify admins - create only ONE notification for admin team
        admin_result = await db.execute(
            select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        )
        admins = admin_result.scalars().all()
        
        if admins:
            # Create ONE notification for admin team (broadcast)
            await NotificationService.create_notification(
                db=db,
                user_id=admins[0].id,
                notification_type="admin_broadcast",
                title="🗑️ Student Deleted",
                message=f"Student '{student_name}' has been deleted from the system.",
                link=f"/admin/students",
                created_by=created_by
            )
        
        return None
