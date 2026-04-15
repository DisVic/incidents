"""
Initialize notification settings for all users
"""
import asyncio
from sqlalchemy import select
from shared.database import async_session
from shared.models import User, Role, NotificationSettings


async def init_notification_settings():
    """Create notification settings for all users with all notifications enabled"""
    async with async_session() as db:
        # Get all users
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        created_count = 0
        updated_count = 0
        
        for user in users:
            # Check if settings already exist
            existing = await db.execute(
                select(NotificationSettings).where(NotificationSettings.user_id == user.id)
            )
            ns = existing.scalar_one_or_none()
            
            # Get user role
            role_result = await db.execute(
                select(Role).where(Role.id == user.role_id)
            )
            role = role_result.scalar_one_or_none()
            role_name = role.name if role else "Executor"
            
            # Define default settings based on role
            all_enabled = {
                "internal": True, 
                "email": True
            }
            
            if role_name == "Admin":
                # Admin gets all notifications
                settings = {
                    "incident_created": all_enabled,
                    "assigned_executor": all_enabled,
                    "new_comment": all_enabled,
                    "status_changed": all_enabled,
                    "incident_resolved": all_enabled,
                    "overdue": all_enabled,
                    "escalation": all_enabled
                }
            elif role_name == "Manager":
                # Manager gets all notifications
                settings = {
                    "incident_created": all_enabled,
                    "assigned_executor": all_enabled,
                    "new_comment": all_enabled,
                    "status_changed": all_enabled,
                    "incident_resolved": all_enabled,
                    "overdue": all_enabled,
                    "escalation": all_enabled
                }
            else:
                # Executor gets most notifications
                settings = {
                    "incident_created": {"internal": True, "email": False},
                    "assigned_executor": all_enabled,
                    "new_comment": all_enabled,
                    "status_changed": all_enabled,
                    "incident_resolved": all_enabled,
                    "overdue": {"internal": True, "email": False},
                    "escalation": {"internal": True, "email": False}
                }
            
            if ns:
                # Update existing
                for key, value in settings.items():
                    setattr(ns, key, value)
                updated_count += 1
            else:
                # Create new
                ns = NotificationSettings(
                    user_id=user.id,
                    **settings
                )
                db.add(ns)
                created_count += 1
        
        await db.commit()
        print(f"Created {created_count} new settings, updated {updated_count} existing settings")
        return {"created": created_count, "updated": updated_count}


if __name__ == "__main__":
    asyncio.run(init_notification_settings())
