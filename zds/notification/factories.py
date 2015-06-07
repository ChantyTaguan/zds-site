import factory
from zds.notification.models import Subscription


class SubscriptionFactory(factory.DjangoModelFactory):
    FACTORY_FOR = Subscription
