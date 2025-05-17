from django.db.models import Avg, Count, Q  # noqa: F401
from django.utils import timezone
from rest_framework import serializers

from events.models import Event, Rating, Tag
from users.serializers import UserSerializer


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class EventListSerializer(serializers.ModelSerializer):
    available_seats = serializers.SerializerMethodField()
    organizer_name = serializers.CharField(source="organizer.username", read_only=True)
    average_rating = serializers.FloatField(source="get_average_rating", read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    is_booked = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "start_at",
            "city",
            "status",
            "available_seats",
            "organizer_name",
            "average_rating",
            "tags",
            "is_booked",
        ]

    def get_available_seats(self, obj):
        if hasattr(obj, "active_bookings_count"):
            return obj.seats - obj.active_bookings_count
        return obj.seats - obj.bookings.filter(cancelled_at__isnull=True).count()

    def get_is_booked(self, obj):
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        return obj.bookings.filter(user=user, cancelled_at__isnull=True).exists()


class EventDetailSerializer(serializers.ModelSerializer):
    available_seats = serializers.SerializerMethodField()
    organizer = UserSerializer(read_only=True)
    average_rating = serializers.FloatField(source="get_average_rating", read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    is_booked = serializers.SerializerMethodField()
    can_be_rated = serializers.SerializerMethodField()
    can_be_deleted = serializers.BooleanField(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "start_at",
            "city",
            "seats",
            "status",
            "available_seats",
            "organizer",
            "created_at",
            "updated_at",
            "average_rating",
            "tags",
            "is_booked",
            "can_be_rated",
            "can_be_deleted",
        ]

    def get_available_seats(self, obj):
        return obj.seats - obj.bookings.filter(cancelled_at__isnull=True).count()

    def get_is_booked(self, obj):
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        return obj.bookings.filter(user=user, cancelled_at__isnull=True).exists()

    def get_can_be_rated(self, obj):
        user = self.context["request"].user
        if not user.is_authenticated:
            return False

        # Можно оценить, если событие завершено и пользователь посещал его
        return (
            obj.status == Event.Status.FINISHED
            and obj.bookings.filter(user=user, cancelled_at__isnull=True).exists()
        )


class EventCreateUpdateSerializer(serializers.ModelSerializer):
    tags = serializers.SlugRelatedField(
        slug_field="slug", queryset=Tag.objects.all(), many=True, required=False
    )

    class Meta:
        model = Event
        fields = ["title", "description", "start_at", "city", "seats", "status", "tags"]

    def validate_start_at(self, value):
        """Проверяет, что дата начала события в будущем"""
        if value <= timezone.now():
            raise serializers.ValidationError(
                "Дата начала события должна быть в будущем"
            )
        return value

    def validate_status(self, value):
        """Проверяет, что статус события валидный"""
        # При создании нового события можно указать только EXPECTED
        if not self.instance and value != Event.Status.EXPECTED:
            raise serializers.ValidationError(
                "При создании события можно указать только статус 'Ожидается'"
            )
        return value


class RatingSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Rating
        fields = ["id", "user", "score", "comment", "created_at"]
        read_only_fields = ["user", "created_at"]

    def validate(self, data):
        """Проверяет, что пользователь может оценить событие"""
        event = self.context.get("event")
        user = self.context.get("request").user

        # Проверяем, что событие завершено
        if event.status != Event.Status.FINISHED:
            raise serializers.ValidationError(
                "Можно оценивать только завершенные события"
            )

        # Проверяем, что пользователь посещал событие
        attended = event.bookings.filter(user=user, cancelled_at__isnull=True).exists()

        if not attended:
            raise serializers.ValidationError("Вы не посещали это событие")

        return data
