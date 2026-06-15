from django.db.models.signals import post_save #signal trigger after a model is being save
from django.dispatch import receiver #receiver towards the register as a signal handler
from django.contrib.auth.models import User #default authentication model kit
from .models import Profile #profile model linked to user


# signal receiver function that runs after a user object is saved
"""...

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    
        #create a signal that automatically create a profile whenever a new User is created
        #sender - the model class (In this case, User)
        #instance - the actual instance being saved
        #created - a boolean, true if a new record was created
        #kwargs - extra keyword arguments
    
    if created:
        Profile.objects.create(user=instance)
...
"""

"""
@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

"""