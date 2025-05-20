# events/serializers.py
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
    is_booked = serializers.SerializerMethodField()
    average_rating = serializers.DecimalField(
        max_digits=3,
        decimal_places=2,
        read_only=True,
    )
    organizer_name = serializers.SerializerMethodField()

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
        return obj.seats - getattr(obj, "active_bookings_count", 0)

    def get_organizer_name(self, obj):
        return obj.organizer.username if obj.organizer else ""

    def get_is_booked(self, obj):
        user = self.context["request"].user
        if user.is_authenticated:
            return obj.bookings.filter(user=user, cancelled_at__isnull=True).exists()
        return False


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
        if not self.instance and value != Event.Status.EXPECTED:
            raise serializers.ValidationError(
                "При создании события можно указать только статус 'Ожидается'"
            )
        return value


class RatingSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    score = serializers.IntegerField(required=False, min_value=1, max_value=10)
    comment = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Rating
        fields = ["id", "user", "score", "comment", "created_at", "updated_at"]
        read_only_fields = ["user", "created_at", "updated_at"]

    def validate(self, attrs):
        if self.instance is None and "score" not in attrs:
            raise serializers.ValidationError("Score is required for new ratings")
        return attrs

    def validate_score(self, value):
        if value is None:
            return value
        if not (1 <= value <= 10):
            raise serializers.ValidationError("Score must be between 1 and 10")
        return value


class EventTagsSerializer(serializers.Serializer):
    tags = serializers.SlugRelatedField(
        slug_field="slug", queryset=Tag.objects.all(), many=True, required=True
    )

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass

    def validate_tags(self, value):
        if not value:
            raise serializers.ValidationError("Необходимо указать хотя бы один тег")
        return value
