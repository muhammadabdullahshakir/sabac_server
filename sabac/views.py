from django.db.models.functions import TruncWeek, TruncDay, TruncMonth
from django.db.models import Count
from django.contrib.auth import get_user_model
from testcase import my_default_json, merge_json
from time import timezone
from django.utils.timezone import localtime, now
from venv import logger
from django.db.models import Q
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
import json
from django.http import JsonResponse
import cloudinary.api
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .serializers import (
    UserSerializer,
    SalerCarDetailsSerializer,
    AvailabilitySerializer,
    SelectedSlotSerializer,
    InspectionReportSerializer,
    BiddingSerializer,
    NotificationSerializer,
    AssignedSlotSerializer,
    AdditionalDetailSerializer,
    GuestSerializer,
)
from .models import (
    User,
    saler_car_details,
    Availability,
    SelectedSlot,
    InspectionReport,
    Bidding,
    Notification,
    AssignSlot,
    Guest,
    DeviceToken,
)
from rest_framework import status
from datetime import datetime, timedelta
from django.utils.timezone import now
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
import logging
from django.db.models import Max
from rest_framework_simplejwt.tokens import RefreshToken
import os
from django.conf import settings


logger = logging.getLogger(__name__)

file_path = os.path.join(settings.BASE_DIR, 'cars.json')
with open(file_path,'r') as f:
    car_data = json.load(f)
    
@csrf_exempt
def get_cars_data(request):
    make = request.GET.get("make")
    year = request.GET.get("year")
    model = request.GET.get("model")
    
    if not make:
        return JsonResponse(car_data)
    
    if make not in car_data:
        return JsonResponse({"error" : "make not foud"},status=status.HTTP_404_NOT_FOUND)
    
    if not year:
        return JsonResponse(car_data[make])
    
    if year not in car_data[make]:
        return JsonResponse({"error" : "invalid Year"},status=status.HTTP_404_NOT_FOUND)
    
    if not model:
        return JsonResponse(car_data[make][year])

    if model not in car_data[make][year]:
        return JsonResponse({"error": "Model not found"}, status=404)

    return JsonResponse({model: car_data[make][year][model]})
    
    
    
    
# login
class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        try:
            username_or_email = request.data.get("username_or_email")
            device_id = request.data.get("device_id")

            if not device_id:
                return Response(
                    {"success": False, "message": "device_id is required"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if "@" in username_or_email:
                user = User.objects.get(email=username_or_email)
            else:
                user = User.objects.get(username=username_or_email)

            request.data["username"] = user.username

            if user.role == "dealer":
                existing_devices = DeviceToken.objects.filter(user=user)

                if (
                    existing_devices.count() >= 3
                    and not existing_devices.filter(device_id=device_id).exists()
                ):
                    return Response(
                        {
                            "success": False,
                            "message": "Maximum number of devices reached. Please logout from another device to continue.",
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

            response = super().post(request, *args, **kwargs)
            if response.status_code != 200 or "access" not in response.data:
                return Response(
                    {"success": False, "message": "Invalid credentials"}, status=401
                )

            tokens = response.data

            token_entry, created = DeviceToken.objects.update_or_create(
                user=user,
                device_id=device_id,
                defaults={"token": tokens["refresh"]},
            )

            user_serializer = UserSerializer(user)

            res = Response(
                {
                    "success": True,
                    "access_token": tokens["access"],
                    "refresh_token": tokens["refresh"],
                    "user": user_serializer.data,
                }
            )

            res.set_cookie(
                key="access_token",
                value=tokens["access"],
                httponly=True,
                secure=True,
                samesite="Lax",
                path="/",
            )
            res.set_cookie(
                key="refresh_token",
                value=tokens["refresh"],
                httponly=True,
                secure=True,
                samesite="Lax",
                path="/",
            )

            return res

        except ObjectDoesNotExist:
            return Response({"success": False, "error": "User not found"}, status=404)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=400)


# refreshing the access token
class CustomRefreshTokenView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        try:
            refresh_token = request.COOKIES.get("refresh_token")
            if not refresh_token:
                return Response({"refreshed": False, "error": "No refresh token found"})

            request.data["refresh"] = refresh_token
            response = super().post(request, *args, **kwargs)
            tokens = response.data

            res = Response()
            res.data = {"refreshed": True, "access_token": tokens["access"]}

            res.set_cookie(
                key="access_token",
                value=tokens["access"],
                httponly=True,
                secure=True,
                samesite="Lax",
                path="/",
            )
            return res
        except Exception as e:
            return Response({"refreshed": False, "error": str(e)})


# LOgout
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    try:
        refresh_token = request.data.get("refresh_token")
        device_id = request.data.get("device_id")

        if not refresh_token or not device_id:
            return Response(
                {"success": False, "error": "refresh_token and device_id are required"},
                status=400,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({"success": False, "error": "Invalid token"}, status=400)

        DeviceToken.objects.filter(user=request.user, device_id=device_id).delete()

        response = Response({"success": True, "message": "Logged out successfully"})
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")

        return response

    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=400)


# for check authentecated
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def is_authentecated(request):
    return Response({"authentecation": True})


# ////////////////////////////////////////ADMIN APIs///////////////////////////////////////////////////////////


# cars count with status bidding
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_cars_count(request):
    try:
        user = request.user
        if user.role.lower() != "admin":
            return Response(
                {"message": "Only admin can view this."},
                status=status.HTTP_403_FORBIDDEN,
            )
        total_cars = saler_car_details.objects.all().count()
        bidding_cars_count = saler_car_details.objects.filter(status="bidding").count()
        pending_cars_count = saler_car_details.objects.filter(status="pending").count()
        sold_cars = saler_car_details.objects.filter(status="sold").count()

        return Response(
            {
                "bidding_cars_count": bidding_cars_count,
                "total_cars": total_cars,
                "pending_cars_count": pending_cars_count,
                "sold_cars": sold_cars,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# get highest bid
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_highest_bid(request):
    try:
        user = request.user
        if user.role != "admin":
            return Response(
                {"message": "only admin can view"}, status=status.HTTP_403_FORBIDDEN
            )

        highest_bid = Bidding.objects.aggregate(Max("bid_amount"))["bid_amount__max"]

        if highest_bid is None:
            return Response({"highest_bid_amount": 0}, status=status.HTTP_200_OK)

        return Response({"highest_bid_amount": highest_bid}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# get list of cars accepted or rejected
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_reviewd_inspection(request):
    try:
        user = request.user
        if user.role != "admin":
            return Response(
                {"message": "only admin can view"}, status=status.HTTP_403_FORBIDDEN
            )
        cars = saler_car_details.objects.filter(
            Q(is_accepted=True) | Q(is_rejected=True)
        )

        serializer = SalerCarDetailsSerializer(cars, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# car list with status awaiting approval
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_cars_for_approval(request):
    try:
        cars = saler_car_details.objects.filter(status="await_approval")

        if not cars.exists():
            return Response(
                {"message": "car not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = SalerCarDetailsSerializer(cars, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ADMIN ACCEPT THE CAR INSPECTION REPORT OF SELLER
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approve_inspection(request, report_id):
    report = get_object_or_404(InspectionReport, id=report_id)

    if report.saler_car and report.saler_car.status == "await_approval":
        report.saler_car.status = "bidding"
        report.saler_car.save()
        
        # notification for seller
        Notification.objects.create(
            recipient = report.saler_car.user,
            message=f"Your car '{report.saler_car.car_name} ({report.saler_car.year})' has been approved for bidding.",
            category="car_approved",
            saler_car=report.saler_car,
        )
        
        # Notify All Dealers
        dealers = User.objects.filter(role="dealer")
        for dealer in dealers:
            Notification.objects.create(
                recipient=dealer,
                message=f"A new car '{report.saler_car.car_name} ({report.saler_car.year})' is now available for bidding.",
                category="dealer_new_bid_car",
                saler_car=report.saler_car,
            )
                    
        return Response(
            {"message": "Seller car approved and moved to bidding"},
            status=status.HTTP_200_OK,
        )

    return Response(
        {"message": "Seller car is not in await_approval status or not linked properly"},
        status=status.HTTP_400_BAD_REQUEST,
    )
    
    

# ADMIN REJECT THE CAR INSPECTION REPORT OF SELLER 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reject_inspection(request, report_id):
        report = get_object_or_404(InspectionReport, id=report_id)

        if report.saler_car and report.saler_car.status == "await_approval":
            report.saler_car.status = "rejected"
            report.saler_car.save()
            # notification for seller
            Notification.objects.create(
                recipient = report.saler_car.user,
                message=f"Your car '{report.saler_car.car_name} ({report.saler_car.year})' has been rejected for bidding.",
                category="car_rejected",
                saler_car=report.saler_car,
            )
                        
            return Response(
                {"message": "Seller car inspection rejected"},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"message": "Seller car is not in await_approval status or not linked properly"},
            status=status.HTTP_400_BAD_REQUEST,
        )


# get the list of all cars by sellers TOTAL CARS IN DATABSE NOT USED
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_cars_list(request):

    cars = saler_car_details.objects.all()
    serializer = SalerCarDetailsSerializer(cars, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ADMIN REGISTER THE DEALER AND INSPECTOR ----NOT USED
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register(request):
    allowed_roles = ["dealer", "inspector", "admin"]

    role = request.data.get("role")

    if role not in allowed_roles:
        return ValidationError(
            {"role": f"invalid Role. Allowed Roles are: {','.join(allowed_roles)}"}
        )

    serializer = UserSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors)


# ADMIN UPDATE THE SALER & INSPECTOR------NOT USED
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def edit_user(request):
    admin = request.user

    user_id = request.data.get("id")
    if not user_id:
        return Response(
            {"message": "User ID is required to edit a user."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user_to_edit = User.objects.get(id=user_id)

        if user_to_edit != admin and admin.role != "admin":
            return Response(
                {"message": "Only admins can edit other users."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data
        user_to_edit.username = data.get("username", user_to_edit.username)
        user_to_edit.first_name = data.get("first_name", user_to_edit.first_name)
        user_to_edit.last_name = data.get("last_name", user_to_edit.last_name)
        user_to_edit.email = data.get("email", user_to_edit.email)
        user_to_edit.phone_number = data.get("phone_number", user_to_edit.phone_number)

        if user_to_edit != admin:
            new_role = data.get("role")
            allowed_roles = ["dealer", "inspector", "admin"]
            if new_role and new_role in allowed_roles:
                user_to_edit.role = new_role
            elif new_role:
                return Response(
                    {
                        "message": f"Invalid role. Allowed roles are: {', '.join(allowed_roles)}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        user_to_edit.save()

        return Response(
            {
                "message": "User updated successfully.",
                "id": user_to_edit.id,
                "username": user_to_edit.username,
                "first_name": user_to_edit.first_name,
                "last_name": user_to_edit.last_name,
                "email": user_to_edit.email,
                "phone_number": user_to_edit.phone_number,
                "role": user_to_edit.role,
            },
            status=status.HTTP_200_OK,
        )
    except User.DoesNotExist:
        return Response(
            {"message": "User not found."}, status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"message": f"Error updating user: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )


# ADMIN DELETE THE USERS
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_user(request):
    admin = request.user

    if admin.role != "admin":
        return Response({"message": "only admin can delete"})

    user_id = request.data.get("id")
    if not user_id:
        return Response({"message": "user Id is required to delete user"})

    try:
        user_to_delete = User.objects.get(id=user_id)

        user_to_delete.delete()

        return Response(
            {"message": f"user with ID {user_id} deleted successfully"},
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# get LIST OF ALL users
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def usersList(request):
    try:

        if not request.user.is_authenticated:
            return Response(
                {"success": False, "message": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if request.user.role != "admin":
            logger.warning(f"Unauthorized access attempt by user: {request.user.email}")
            return Response(
                {
                    "success": False,
                    "message": "You are not authorized. Only admins can access this resource.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        users = User.objects.all().only("id", "email", "role", "username")

        serializer = UserSerializer(users, many=True)

        return Response(
            {
                "success": True,
                "users": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Error in usersList API: {str(e)}", exc_info=True)
        return Response(
            {
                "success": False,
                "message": "An unexpected error occurred while fetching users.",
                "error": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# list of dealrs
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dealersList(request):
    try:
        if not request.user.is_authenticated:
            return Response(
                {"success": False, "message": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if request.user.role != "admin":
            logger.warning(f"Unauthorized access attempt by user: {request.user.email}")
            return Response(
                {
                    "success": False,
                    "message": "You are not authorized. Only admins can access this resource.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        users = User.objects.filter(role="dealer")

        serializer = UserSerializer(users, many=True)

        return Response(
            {
                "success": True,
                "dealers": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Error in usersList API: {str(e)}", exc_info=True)
        return Response(
            {
                "success": False,
                "message": "An unexpected error occurred while fetching users.",
                "error": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# list of inspectors
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def inspectorsList(request):
    try:
        if not request.user.is_authenticated:
            return Response(
                {"success": False, "message": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if request.user.role != "admin":
            logger.warning(f"Unauthorized access attempt by user: {request.user.email}")
            return Response(
                {
                    "success": False,
                    "message": "You are not authorized. Only admins can access this resource.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        users = User.objects.filter(role="inspector")

        serializer = UserSerializer(users, many=True)

        return Response(
            {
                "success": True,
                "inspectors": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Error in API: {str(e)}", exc_info=True)
        return Response(
            {
                "success": False,
                "message": "An unexpected error occurred while fetching users.",
                "error": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# list of admins
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def adminList(request):
    try:
        if not request.user.is_authenticated:
            return Response(
                {"success": False, "message": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if request.user.role != "admin":
            logger.warning(f"Unauthorized access attempt by user: {request.user.email}")
            return Response(
                {
                    "success": False,
                    "message": "You are not authorized. Only admins can access this resource.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        users = User.objects.filter(role="admin")

        serializer = UserSerializer(users, many=True)

        return Response(
            {
                "success": True,
                "admins": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Error in API: {str(e)}", exc_info=True)
        return Response(
            {
                "success": False,
                "message": "An unexpected error occurred while fetching users.",
                "error": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# count of users
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_count(request):
    try:
        if request.user.role != "admin":
            return Response(
                {"message": "only admin can access"}, status=status.HTTP_403_FORBIDDEN
            )

        total = User.objects.count()
        sellers = User.objects.filter(role="saler").count()
        inspector = User.objects.filter(role="inspector").count()
        dealer = User.objects.filter(role="dealer").count()
        admin = User.objects.filter(role="admin").count()

        data = {
            "total_users": total,
            "sellers": sellers,
            "inspector": inspector,
            "dealer": dealer,
            "admin": admin,
        }

        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# count of cars
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_cars_count(request):
    try:
        if request.user.role != "admin":
            return Response(
                {"message": "Only admin can access"}, status=status.HTTP_403_FORBIDDEN
            )

        total = saler_car_details.objects.count()
        pending = saler_car_details.objects.filter(status="pending").count()
        assigned = saler_car_details.objects.filter(status="assigned").count()
        in_inspection = saler_car_details.objects.filter(status="in_inspection").count()
        awaiting_approval = saler_car_details.objects.filter(
            status="await_approval"
        ).count()
        rejected = saler_car_details.objects.filter(status="rejected").count()
        bidding = saler_car_details.objects.filter(status="bidding").count()
        expired = saler_car_details.objects.filter(status="expired").count()
        sold = saler_car_details.objects.filter(status="sold").count()

        data = {
            "total_cars": total,
            "pending": pending,
            "assigned": assigned,
            "in_inspection": in_inspection,
            "awaiting_approval": awaiting_approval,
            "rejected": rejected,
            "bidding": bidding,
            "expired": expired,
            "sold": sold,
        }
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# car posting graph daily weekly
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def carsStats(request):
    range_type = request.GET.get("range", "daily")
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")

    queryset = saler_car_details.objects.all()

    if from_date and to_date:
        try:
            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d")
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d")
            queryset = queryset.filter(
                created_at__date__gte=from_date_obj, created_at__date__lte=to_date_obj
            )
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    if range_type == "weekly":
        queryset = queryset.annotate(period=TruncWeek("created_at"))

    elif range_type == "monthly":
        queryset = queryset.annotate(period=TruncMonth("created_at"))

    elif range_type == "15days":
        queryset = queryset.extra(
            select={
                "period": "DATE_TRUNC('day', created_at) - INTERVAL '1 day' * (EXTRACT(DAY FROM created_at)::int % 15)"
            }
        )

    elif range_type == "3months":
        queryset = queryset.extra(
            select={
                "period": "DATE_TRUNC('month', created_at) - INTERVAL '1 month' * (EXTRACT(MONTH FROM created_at)::int % 3)"
            }
        )

    elif range_type == "6months":
        queryset = queryset.extra(
            select={
                "period": "DATE_TRUNC('month', created_at) - INTERVAL '1 month' * (EXTRACT(MONTH FROM created_at)::int % 6)"
            }
        )

    elif range_type == "1year":
        queryset = queryset.extra(select={"period": "DATE_TRUNC('year', created_at)"})

    elif range_type == "complete":
        total = queryset.count()
        return Response(
            [{"period": "Complete", "count": total}], status=status.HTTP_200_OK
        )

    else:
        queryset = queryset.annotate(period=TruncDay("created_at"))

    data = (
        queryset.values("period")
        .annotate(count=Count("saler_car_id"))
        .order_by("period")
    )
    return Response(data, status=status.HTTP_200_OK)


# ACCEPT BID
# @api_view(["POST"])
# @permission_classes([IsAuthenticated])
# def accept_bid(request, bid_id):
#     user = request.user
#     logger.info(f"User {user.username} is attempting to accept bid {bid_id}")

#     if user.role != "admin":
#         return Response(
#             {"message": "Only admins can accept bids"},
#             status=status.HTTP_403_FORBIDDEN,
#         )

#     try:
#         bid = Bidding.objects.get(id=bid_id)
#     except Bidding.DoesNotExist:
#         logger.error(f"Bid with id {bid_id} not found.")
#         return Response({"message": "Bid not found"}, status=status.HTTP_404_NOT_FOUND)

#     if bid.status != "pending":
#         return Response(
#             {"message": "Bid already processed"}, status=status.HTTP_400_BAD_REQUEST
#         )

#     bid.is_accepted = True
#     bid.status = "accepted"
#     bid.save()

#     car = bid.saler_car
#     car.is_sold = True
#     car.winner_dealer = bid.dealer
#     car.save()

#     Bidding.objects.filter(saler_car=car).exclude(id=bid_id).update(status="rejected")

#     Notification.objects.create(
#         recipient=bid.dealer,
#         message=f"Your bid of {bid.bid_amount} on {car.company} {car.car_name} {car.year} has been accepted.",
#         saler_car=car,
#         bid=bid,
#         category="bid_accepted",
#     )

#     return Response(
#         {"message": "Bid accepted and car marked as sold"},
#         status=status.HTTP_200_OK,
#     )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def accept_bid(request, bid_id):
    user = request.user
    if user.role != "admin":
        return Response(
            {"message": "Only admins can accept bids"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        bid = Bidding.objects.get(id=bid_id)
    except Bidding.DoesNotExist:
        return Response({"message": "Bid not found"}, status=status.HTTP_404_NOT_FOUND)

    if bid.status != "pending":
        return Response(
            {"message": "Bid already processed"}, status=status.HTTP_400_BAD_REQUEST
        )

    bid.is_accepted = True
    bid.status = "accepted"
    bid.save()

    car = bid.saler_car or bid.guest_car
    car.is_sold = True
    car.winner_dealer = bid.dealer
    car.save()

    # Reject other bids
    if bid.saler_car:
        Bidding.objects.filter(saler_car=car).exclude(id=bid_id).update(status="rejected")
    elif bid.guest_car:
        Bidding.objects.filter(guest_car=car).exclude(id=bid_id).update(status="rejected")

    Notification.objects.create(
        recipient=bid.dealer,
        message=f"Your bid of {bid.bid_amount} on {car.company} {car.car_name} {car.year} has been accepted.",
        saler_car=bid.saler_car,
        guest_car=bid.guest_car,
        bid=bid,
        category="bid_accepted",
    )
    Notification.objects.create(
        recipient=car.user,
        message=f"Your car {car.company} {car.car_name} {car.year} has been sold.",
        category="car_sold",
        saler_car=car
    )

    return Response(
        {"message": "Bid accepted and car marked as sold"},
        status=status.HTTP_200_OK,
    )






# REJECT BID
# @api_view(["POST"])
# @permission_classes([IsAuthenticated])
# def reject_bid(request, bid_id):
#     user = request.user
#     logger.info(f"User {user.username} is attempting to reject bid {bid_id}")

#     if user.role != "admin":
#         return Response(
#             {"message": "Only admins can reject bids"},
#             status=status.HTTP_403_FORBIDDEN,
#         )

#     bid = get_object_or_404(Bidding, id=bid_id)

#     if bid.status != "pending":
#         logger.info(f"Bid {bid_id} has already been processed with status {bid.status}")
#         return Response(
#             {"message": "Bid has already been processed"},
#             status=status.HTTP_400_BAD_REQUEST,
#         )

#     bid.is_accepted = False
#     bid.status = "rejected"
#     bid.save()

#     car = bid.saler_car

#     Notification.objects.create(
#         recipient=bid.dealer,
#         message=f"Your bid of {bid.bid_amount} on {car.company} {car.car_name} {car.year} has been rejected.",
#         saler_car=car,
#         bid=bid,
#         category="bid_rejected",
#     )

#     logger.info(f"Bid {bid_id} rejected successfully by admin {user.username}")
#     return Response({"message": "Bid rejected"}, status=status.HTTP_200_OK)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reject_bid(request, bid_id):
    user = request.user
    if user.role != "admin":
        return Response(
            {"message": "Only admins can reject bids"},
            status=status.HTTP_403_FORBIDDEN,
        )

    bid = get_object_or_404(Bidding, id=bid_id)

    if bid.status != "pending":
        return Response(
            {"message": "Bid has already been processed"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    bid.is_accepted = False
    bid.status = "rejected"
    bid.save()

    car = bid.saler_car or bid.guest_car

    Notification.objects.create(
        recipient=bid.dealer,
        message=f"Your bid of {bid.bid_amount} on {car.company} {car.car_name} {car.year} has been rejected.",
        saler_car=bid.saler_car,
        guest_car=bid.guest_car,
        bid=bid,
        category="bid_rejected",
    )

    return Response({"message": "Bid rejected"}, status=status.HTTP_200_OK)






# FETCH BID NOTIFICATION FOR admin not used
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bid_notification(request):
    user = request.user

    if user.role != "admin":
        return Response(
            {"message": "Only admin can view notifications"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        unread_notifications = Notification.objects.filter(
            recipient=user, category="new_bid", is_read=False
        ).order_by("-created_at")

        serializer = NotificationSerializer(unread_notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"message": f"Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# FETCH BID NOTIFICATION FOR admin
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bid_notification_for_seller(request):
    user = request.user
    if user.role != "admin":
        return Response(
            {"message": "Only admin can view notifications"},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        unread_notifications = Notification.objects.filter(
            recipient=user, category="new_bid", is_read=False
        ).order_by("-created_at")
        serializer = NotificationSerializer(unread_notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"message": f"Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_bid_notifications_as_read(request):
    user = request.user
    if user.role != "admin":
        return Response(
            {"message": "Only admins can update bid notifications"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        notification_ids = request.data.get("notification_ids", [])

        if not notification_ids:
            return Response(
                {"message": "No notifications to mark as read"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_count = Notification.objects.filter(
            id__in=notification_ids, recipient=user, category="new_bid"
        ).update(is_read=True)

        return Response(
            {"message": f"{updated_count} notifications marked as read"},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"message": f"Error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# admin view all bids
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_bidding(request):
    user = request.user

    if user.role != "admin":
        return Response(
            {"success": False, "message": "Only admin can view all bids."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:

        bids = Bidding.objects.select_related("dealer", "saler_car", "saler_car__user")

        serializer = BiddingSerializer(bids, many=True)

        return Response(
            {
                "success": True,
                "message": "All bids fetched successfully.",
                "bids": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Error fetching all bids for admin: {str(e)}", exc_info=True)
        return Response(
            {
                "success": False,
                "message": "An unexpected error occurred while fetching bids.",
                "error": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# admin view all sold cars
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_sold_cars(request):

    sold_cars = saler_car_details.objects.filter(status="sold", is_sold=True)

    result = []

    for car in sold_cars:
        accepted_bid = Bidding.objects.filter(saler_car=car, is_accepted=True).first()

        result.append(
            {
                "car_id": car.saler_car_id,
                "car_name": car.car_name,
                "company": car.company,
                "photos": car.photos if car.photos else [],
                "year": car.year,
                "owner": (
                    {
                        "id": car.user.id,
                        "username": car.user.username,
                        "first_name": car.user.first_name,
                        "last_name": car.user.last_name,
                        "adress": car.user.adress,
                        "number": car.user.phone_number,
                    }
                    if car.user
                    else None
                ),
                "winner_dealer": (
                    {
                        "id": car.winner_dealer.id,
                        "username": car.winner_dealer.username,
                        "first_name": car.winner_dealer.first_name,
                        "last_name": car.winner_dealer.last_name,
                        "adress": car.winner_dealer.adress,
                        "number": car.winner_dealer.phone_number,
                    }
                    if car.winner_dealer
                    else None
                ),
                "accepted_bid_amount": (
                    str(accepted_bid.bid_amount) if accepted_bid else None
                ),
                "accepted_bid_date": accepted_bid.bid_date if accepted_bid else None,
            }
        )
        return Response(result)


# /////////////////////////////////////SELLER APIs/////////////////////////////////////////


# seller post car detail
# @api_view(["POST"])
# @permission_classes([IsAuthenticated])
# def add_car_details(request):
#     try:
#         user = request.user
#         data = request.data.copy()
#         data["user"] = user.id
#         data["added_by"] = "seller"

#         serializer = SalerCarDetailsSerializer(data=data)
#         if serializer.is_valid():
#             car_details = serializer.save()

#             saler_phone_number = getattr(user, "phone_number", "N/A")

#             inspection_date = (
#                 car_details.inspection_date.strftime("%Y-%m-%d")
#                 if car_details.inspection_date
#                 else "Not Scheduled"
#             )
#             inspection_time = car_details.inspection_time 

#             inspectors = User.objects.filter(role="inspector")

#             for inspector in inspectors:
#                 message = (
#                     f"New Car: {car_details.car_name} ({car_details.year}) "
#                     f"Added by: {user.username} (Phone: {saler_phone_number})."
#                 )

#                 if inspection_date and inspection_time:
#                     message += f" Inspection Scheduled on {inspection_date} at {inspection_time}."
#                 else:
#                     message += " Inspection schedule not set."

#                 Notification.objects.create(
#                     recipient=inspector,
#                     message=message,
#                     category="saler_car_details",
#                 )


#             return Response(serializer.data, status=status.HTTP_201_CREATED)

#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     except Exception as e:
#         return Response(
#             {"success": False, "message": f"Error adding car details: {str(e)}"},
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#         )



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_car_details(request):
    try:
        user = request.user
        data = request.data.copy()
        data["user"] = user.id
        data["added_by"] = "seller"

        serializer = SalerCarDetailsSerializer(data=data)
        if serializer.is_valid():
            car_details = serializer.save()

            saler_phone_number = getattr(user, "phone_number", "N/A")

            inspection_date = car_details.inspection_date
            inspection_time = car_details.inspection_time

            inspectors = User.objects.filter(role="inspector")

            for inspector in inspectors:
                message = (
                    f"New Car: {car_details.car_name} ({car_details.year}) "
                    f"Added by: {user.username} (Phone: {saler_phone_number}). "
                )

                if inspection_date and inspection_time:
                    message += f"Inspection Scheduled on {inspection_date} at {inspection_time}."
                else:
                    message += "No appointment scheduled."

                Notification.objects.create(
                    recipient=inspector,
                    message=message,
                    category="saler_car_details",
                )

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response(
            {"success": False, "message": f"Error adding car details: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# seller select slot
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def select_slot(request):
    user = request.user
    data = request.data

    required_fields = ["saler_car_id", "availability_id", "time_slot"]
    for field in required_fields:
        if field not in data:
            return Response(
                {"message": f"Missing required field: {field}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    try:
        saler_car = saler_car_details.objects.get(
            saler_car_id=data["saler_car_id"], user=user
        )
    except saler_car_details.DoesNotExist:
        return Response(
            {"message": "Car not found or unauthorized"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        availability = Availability.objects.get(id=data["availability_id"])
    except Availability.DoesNotExist:
        return Response(
            {"message": "Availability not found"}, status=status.HTTP_404_NOT_FOUND
        )

    selected_time_slot = data["time_slot"]
    if selected_time_slot not in availability.time_slots:
        return Response(
            {"message": "Selected time slot is not available"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if SelectedSlot.objects.filter(
        inspector=availability.inspector,
        date=availability.date,
        time_slot=selected_time_slot,
    ).exists():
        return Response(
            {"message": "Time slot already booked"}, status=status.HTTP_400_BAD_REQUEST
        )
    selected_slot = SelectedSlot(
        saler_car=saler_car,
        inspector=availability.inspector,
        date=availability.date,
        time_slot=selected_time_slot,
        booked_by="By Seller",
    )
    selected_slot.save()
    availability.time_slots = [
        slot for slot in availability.time_slots if slot != selected_time_slot
    ]
    availability.save()

    notification_message = f"Appointment scheduled for {saler_car.car_name} at {selected_time_slot} on {availability.date}"
    Notification.objects.create(
        recipient=availability.inspector,
        message=notification_message,
        category="seller_time_slot_selection",
    )
    return Response(
        {"message": "Time slot selected successfully"}, status=status.HTTP_201_CREATED
    )
    
    
# get manual entries for seller
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_manual_saler_assigned_slots(request):
    # Filter only manually added cars that are assigned
    saler_slots = AssignSlot.objects.select_related("car", "inspector").filter(
        car__isnull=False,
        car__status="assigned",
        car__is_manual=True
    )

    serializer = AssignedSlotSerializer(saler_slots, many=True)
    return Response({"manual_saler_cars": serializer.data}, status=200)


# additional name and number post view
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def post_additional_details(request):
    serializer = AdditionalDetailSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()
        return Response(
            {"Message": "Data saved", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# list of saler cars
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_cars(request):
    user = request.user

    cars = saler_car_details.objects.filter(user=user).select_related("user")

    if not cars.exists():
        return Response(
            {"error": "No cars found for this user."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = SalerCarDetailsSerializer(cars, many=True)

    return Response({"cars": serializer.data}, status=status.HTTP_200_OK)


# notifciation of appointment
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_appointment_notification(request):

    user = request.user

    notifications = Notification.objects.filter(
        recepient=user, category="inspector_gives_appointment"
    ).order_by("-created_at")

    serializer = NotificationSerializer(notifications, many=True)
    return Response(
        {"message": "Appointment", "notification": serializer.data},
        status=status.HTTP_200_OK,
    )


# SALER UPDATED CAR DETAILS
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_car_details(request, car_id):
    user = request.user

    if user.role != "saler":
        return Response("only Sler can update", status=status.HTTP_400_BAD_REQUEST)

    try:
        saler_car = saler_car_details.objects.get(saler_car_id=car_id, user=user)
    except saler_car_details.DoesNotExist:
        return Response("Car not found", status=status.HTTP_404_NOT_FOUND)

    saler_phone_number = user.phone_number

    old_car_details = saler_car.__dict__.copy()

    serializer = SalerCarDetailsSerializer(saler_car, data=request.data, partial=True)

    if serializer.is_valid():
        updated_car = serializer.save()

        if old_car_details != updated_car.__dict__:
            notifications = Notification.objects.filter(saler_car=saler_car)
            for notification in notifications:
                notification.message = (
                    f"Updated car details for {updated_car.car_name}: "
                    f"New demand {updated_car.demand} and phone number {saler_phone_number}."
                )
                notification.save()

        return Response(
            {"message": "Updated successfully", "result": serializer.data},
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def saler_appointmet(request):
    user = request.user

    if user.role != "saler":
        return Response(
            {"message": "Only sellers can view their appointments"},
            status=status.HTTP_403_FORBIDDEN,
        )

    appointments = saler_car_details.objects.filter(user=user).order_by(
        "inspection_date", "inspection_time"
    )

    if not appointments.exists():
        return Response(
            {"message": "No appointments found for this seller"},
            status=status.HTTP_404_NOT_FOUND,
        )

    serialized_appointments = SalerCarDetailsSerializer(appointments, many=True).data

    for i, appointment in enumerate(appointments):
        serialized_appointments[i]["inspection_date"] = (
            appointment.inspection_date.strftime("%Y-%m-%d")
        )
        serialized_appointments[i]["inspection_time"] = appointment.inspection_time

    return Response(
        {
            "message": "Seller appointments retrieved successfully",
            "appointments": serialized_appointments,
        },
        status=status.HTTP_200_OK,
    )


# Saler appointment Slot assigned by insppector manually
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def saler_manual_entry(request):
    user = request.user
    if user.role != "saler":
        return Response(
            {"Message": "Only Saler can view their appointments"},
            status=status.HTTP_403_FORBIDDEN,
        )

    appointments = AssignSlot.objects.filter(car__user=user).select_related(
        "car", "inspector"
    )

    appointments_data = []

    for appointment in appointments:
        appointment_datetime = timezone.make_aware(
            datetime.combine(appointment.date, appointment.time_slot)
        )
        appointments_data.append(
            {
                "appointment_id": appointment.id,
                "car_id": appointment.car.saler_car_id,
                "car_name": appointment.car.car_name,
                "company": appointment.car.company,
                "car_year": appointment.car.model,
                "is_inspected": appointment.car.is_inspected,
                "appointment_date": appointment.date.strftime("%Y-%m-%d"),
                "car_photos": appointment.car.photos,
                "appointment_time": appointment.time_slot.strftime("%H:%M"),
                "inspector_first_name": appointment.inspector.first_name,
                "inspector_last_name": appointment.inspector.last_name,
                "inspector_phone_number": appointment.inspector.phone_number,
                "inspector_adress": appointment.inspector.adress,
                "inspector_email": appointment.inspector.email,
                "status": appointment.car.status,
                "assigned_by": appointment.assigned_by,
                "created_at": appointment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return Response({"appointments": appointments_data}, status=status.HTTP_200_OK)


# Saler update its details NOT USED NOW
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def saler_update(request):
    user = request.user
    if user.role != "saler":
        return Response(
            {"message": "Only salers can update their details"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = request.data
    user.username = data.get("username", user.username)
    user.first_name = data.get("first_name", user.first_name)
    user.last_name = data.get("last_name", user.last_name)
    user.email = data.get("email", user.email)
    user.phone_number = data.get("phone_number", user.phone_number)

    if "password" in data:
        password = data.get("password")
        if password:
            user.set_password(password)

    try:
        user.save()
        return Response(
            {
                "message": "User updated successfully",
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone_number": user.phone_number,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {"message": f"Error updating user: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )


# user delete its profile NOT USED NOW
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_saler(request):
    user = request.user

    if user.role != "saler":
        return Response(
            {"Message": "saler can delete its data"}, status=status.HTTP_400_BAD_REQUEST
        )

    if request.user.id != user.id:
        return Response(
            {"Message": "You can delete only your data"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user_id = user.id
        user.delete()

        return Response(
            {
                "message": f"User witg ID {user_id} delete successfully",
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response({"Error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# seller register
@api_view(["POST"])
@permission_classes([AllowAny])
def saler_register(request):
    data = request.data

    try:
        user = User.objects.create_user(
            username=data.get("username"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            email=data.get("email"),
            password=data.get("password"),
            phone_number=data.get("phone_number"),
            adress=data.get("adress"),
            image=data.get("image"),
            role="saler",
        )

        return Response(
            {
                "message": "User created successfully",
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "email": user.email,
                "phone_number": user.phone_number,
                "adress": user.adress,  # ✅ return it
                "image": user.image,  # ✅ return it
                "role": user.role,
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# dealer register
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def dealer_register(request):

    if request.user.role != "admin":
        return Response(
            {"message": "Only admin can register a dealer."},
            status=status.HTTP_403_FORBIDDEN,
        )

    data = request.data

    try:
        user = User.objects.create_user(
            username=data.get("username"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            email=data.get("email"),
            password=data.get("password"),
            phone_number=data.get("phone_number"),
            adress=data.get("adress"),
            role="dealer",
        )

        return Response(
            {
                "message": "Dealer created successfully",
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "email": user.email,
                "phone_number": user.phone_number,
                "role": user.role,
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# update dealer
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def dealer_update(request, dealer_id):
    if request.user.role != "admin":
        return Response(
            {"message": "Only admin can update dealer details."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        user = User.objects.get(id=dealer_id, role="dealer")
    except User.DoesNotExist:
        return Response(
            {"message": "Dealer not found."}, status=status.HTTP_404_NOT_FOUND
        )

    data = request.data

    user.username = data.get("username", user.username)
    user.first_name = data.get("first_name", user.first_name)
    user.last_name = data.get("last_name", user.last_name)
    user.email = data.get("email", user.email)
    user.phone_number = data.get("phone_number", user.phone_number)
    user.adress = data.get("adress", user.adress)
    if data.get("password"):
        user.set_password(data["password"])

    user.save()

    return Response(
        {
            "message": "Dealer updated successfully",
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "email": user.email,
            "phone_number": user.phone_number,
            "role": user.role,
        },
        status=status.HTTP_200_OK,
    )


# inspector register
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def inspector_register(request):

    if request.user.role != "admin":
        return Response(
            {"message": "Only admin can register a dealer."},
            status=status.HTTP_403_FORBIDDEN,
        )

    data = request.data

    try:
        user = User.objects.create_user(
            username=data.get("username"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            email=data.get("email"),
            password=data.get("password"),
            phone_number=data.get("phone_number"),
            adress=data.get("adress"),
            role="inspector",
        )

        return Response(
            {
                "message": "inspector created successfully",
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "email": user.email,
                "phone_number": user.phone_number,
                "role": user.role,
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# update inspector
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def inspector_update(request, inspector_id):
    if request.user.role != "admin":
        return Response(
            {"message": "Only admin can update dealer details."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        user = User.objects.get(id=inspector_id, role="inspector")
    except User.DoesNotExist:
        return Response(
            {"message": "Dealer not found."}, status=status.HTTP_404_NOT_FOUND
        )

    data = request.data

    user.username = data.get("username", user.username)
    user.first_name = data.get("first_name", user.first_name)
    user.last_name = data.get("last_name", user.last_name)
    user.email = data.get("email", user.email)
    user.phone_number = data.get("phone_number", user.phone_number)
    user.adress = data.get("adress", user.adress)
    if data.get("password"):
        user.set_password(data["password"])

    user.save()

    return Response(
        {
            "message": "inspector updated successfully",
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "email": user.email,
            "phone_number": user.phone_number,
            "adress": user.adress,
            "role": user.role,
        },
        status=status.HTTP_200_OK,
    )


# admin register
@api_view(["POST"])
@permission_classes([AllowAny])
def admin_register(request):
    data = request.data
    try:
        user = User.objects.create_user(
            username=data.get("username"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            email=data.get("email"),
            password=data.get("password"),
            phone_number=data.get("phone_number"),
            adress=data.get("adress"),
            role="admin",
        )

        return Response(
            {
                "message": "admin created successfully",
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "email": user.email,
                "phone_number": user.phone_number,
                "adress": user.adress,
                "role": user.role,
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# admin update dealer
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def admin_update(request, admin_id):
    if request.user.role != "admin":
        return Response(
            {"message": "Only admin can update dealer details."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        user = User.objects.get(id=admin_id, role="admin")
    except User.DoesNotExist:
        return Response(
            {"message": "Admin not found."}, status=status.HTTP_404_NOT_FOUND
        )
    data = request.data

    user.username = data.get("username", user.username)
    user.first_name = data.get("first_name", user.first_name)
    user.last_name = data.get("last_name", user.last_name)
    user.email = data.get("email", user.email)
    user.phone_number = data.get("phone_number", user.phone_number)
    user.adress = data.get("adress", user.adress)
    if data.get("password"):
        user.set_password(data["password"])

    user.save()

    return Response(
        {
            "message": "admin updated successfully",
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "email": user.email,
            "phone_number": user.phone_number,
            "role": user.role,
        },
        status=status.HTTP_200_OK,
    )


# VIEW BIDS FOR SPECEFIC CAR
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def view_car_bids(request, car_id):
    try:
        car = saler_car_details.objects.get(saler_car_id=car_id)
    except saler_car_details.DoesNotExist:
        return Response({"Message": "car Not found"}, status=status.HTTP_404_NOT_FOUND)

    bids = Bidding.objects.filter(saler_car=car).order_by("-bid_date")

    serializer = BiddingSerializer(bids, many=True)

    return Response(
        {"Message": "Bids Fetched Successgully", "bids": serializer.data},
        status=status.HTTP_200_OK,
    )


# SELLER DELETE ITS CAR
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_ad(request, car_id):
    user = request.user
    print("user requesting for delete:", user)

    try:
        car = saler_car_details.objects.get(saler_car_id=car_id)
    except saler_car_details.DoesNotExist:
        return Response({"message": "car not found"}, status=status.HTTP_404_NOT_FOUND)

    if car.user != user:
        print("car owner:", car.user)
        return Response(
            {"message": "Unauthentecated"}, status=status.HTTP_403_FORBIDDEN
        )

    car.delete()

    return Response({"message": "car deleted successfully"}, status=status.HTTP_200_OK)


# SELLER UPDATED ITS CAR DETAIL
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_ad(request, car_id):
    user = request.user
    data = request.data

    try:
        car = saler_car_details.objects.get(saler_car_id=car_id)
    except saler_car_details.DoesNotExist:
        return Response({"message": "car not found"}, status=status.HTTP_404_NOT_FOUND)

    if car.user != user:
        return Response({"message": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

    serializer = SalerCarDetailsSerializer(car, data, partial=True)

    if serializer.is_valid():
        serializer.save()
        return Response(
            {"message": "car updated successfully", "car": serializer.data},
            status=status.HTTP_200_OK,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Assign inspector to a car (Seller) ON CALL
@api_view(["POST"])
@permission_classes([AllowAny])
def assign_inspector_to_car(request):
    try:
        car_id = request.data.get("car_id")
        inspector_id = request.data.get("inspector_id")

        if not car_id or not inspector_id:
            return Response(
                {"error": "Car ID and Inspector ID are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            inspector = User.objects.get(id=inspector_id, role="inspector")
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid inspector selected"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            car = saler_car_details.objects.get(saler_car_id=car_id)
        except saler_car_details.DoesNotExist:
            return Response(
                {"error": "Car not found"}, status=status.HTTP_404_NOT_FOUND
            )

        car.inspector = inspector
        car.save()

        return Response(
            {"message": "Inspector assigned successfully!"}, status=status.HTTP_200_OK
        )

    except Exception as e:
        print(f"Error in assign_inspector_to_car: {e}")
        return Response(
            {"success": False, "message": f"An error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# GET THE CAR DETAILS OF SALER
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_car_details(request):
    user = request.user

    cars = saler_car_details.objects.filter(user=user)
    if not cars.exists():
        return Response(
            {"detail": "No car details found for this user."},
            status=status.HTTP_404_NOT_FOUND,
        )
    serializer = SalerCarDetailsSerializer(cars, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# lIST OF INSPECTORS
@api_view(["GET"])
@permission_classes([AllowAny])
def get_inspectors(request):
    try:
        inspector = User.objects.filter(role="inspector")
        serializer = UserSerializer(inspector, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# NOT USED
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_list_of_car_for_inspection(request):
    try:
        all_cars = saler_car_details.objects.all()

        serializer = SalerCarDetailsSerializer(all_cars, many=True)

        total_cars = all_cars.count()

        today = now().date()

        cars_today = all_cars.filter(created_at__date=today).count()

        all_cars_progress = 0
        if total_cars > 0:
            all_cars_progress = (cars_today / total_cars) * 100

        response_data = {
            "total_cars": total_cars,
            "cars_today": cars_today,
            "all_cars_progress": round(
                all_cars_progress, 2
            ),  # Round to 2 decimal places
            "cars": serializer.data,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Error in get_list_of_car_for_inspection: {str(e)}")
        return Response(
            {"error": "An error occurred while fetching the car list."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# get the last car details only NOT USED
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_last_car_details(request):
    user = request.user

    last_car = (
        saler_car_details.objects.filter(user=user).order_by("-saler_car_id").first()
    )
    if not last_car:
        return Response(
            {"detail": "No car details found for this user."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = SalerCarDetailsSerializer(last_car)
    return Response(serializer.data, status=status.HTTP_200_OK)

# ///////////////////////////////INSPECTOR APIs////////////////////////////////


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def inspector_appointments(request):
    user = request.user
    if user.role != "inspector":
        return Response(
            {"message": "Only inspectors can view this data"},
            status=status.HTTP_403_FORBIDDEN,
        )

    appointments = saler_car_details.objects.filter(
        inspector=user, user__isnull=False, is_manual=False
    ).order_by("inspection_date", "inspection_time")

    if not appointments.exists():
        return Response(
            {"message": "No valid appointments found for this inspector"},
            status=status.HTTP_404_NOT_FOUND,
        )

    serialized_appointments = SalerCarDetailsSerializer(appointments, many=True).data

    for i, appointment in enumerate(appointments):
        serialized_appointments[i]["inspection_date"] = (
            appointment.inspection_date.strftime("%Y-%m-%d")
        )
        serialized_appointments[i]["inspection_time"] = appointment.inspection_time

    return Response(
        {
            "message": "Inspector appointments retrieved successfully",
            "appointments": serialized_appointments,
        },
        status=status.HTTP_200_OK,
    )


# INSPECTOR ASSIGN SLOTS
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def assign_slot(request):
    data = request.data.copy()
    inspector = request.user

    car_id = data.get("car_id")
    guest_car_id = data.get("guest_car_id")
    inspection_date = data.get("inspection_date")
    inspection_time = data.get("inspection_time")

    if not (car_id or guest_car_id):
        return Response({"error": "Either car_id or guest_car_id is required."}, status=400)

    if not (inspection_date and inspection_time):
        return Response({"error": "Both inspection_date and inspection_time are required."}, status=400)

    try:
        datetime.strptime(inspection_time, "%I:%M %p")
    except ValueError:
        return Response({"error": "Invalid time format. Use 12-hour format like '01:30 PM'."}, status=400)

    # Check availability and update slot
    try:
        availability = Availability.objects.get(inspector=inspector, date=inspection_date)
        formatted_slots = [slot if isinstance(slot, str) else slot.strftime("%I:%M %p") for slot in availability.time_slots]

        if inspection_time in formatted_slots:
            availability.time_slots.remove(inspection_time)
            availability.save()
        else:
            return Response({"error": "Slot not available in inspector's availability."}, status=400)

    except Availability.DoesNotExist:
        return Response({"error": "Inspector availability not found."}, status=404)

    # Create slot and assign
    if car_id:
        try:
            car = saler_car_details.objects.get(pk=car_id)
            car.inspector = inspector
            car.inspection_date = inspection_date
            car.inspection_time = inspection_time
            car.status = "assigned"
            car.save()

            AssignSlot.objects.create(
                inspector=inspector,
                car=car,
                inspection_date=inspection_date,
                inspection_time=inspection_time,
                assigned_by="inspector",
            )

            return Response({
                "message": "Slot assigned successfully",
                "assigned_to": "saler",
                "slot_date": inspection_date,
                "slot_time": inspection_time,
                "inspector": inspector.username,
                "saler_car": SalerCarDetailsSerializer(car).data
            }, status=201)

        except saler_car_details.DoesNotExist:
            return Response({"error": "Invalid saler car ID."}, status=400)

    elif guest_car_id:
        try:
            guest = Guest.objects.get(pk=guest_car_id)
            guest.inspector = inspector
            guest.inspection_date = inspection_date
            guest.inspection_time = inspection_time
            guest.status = "assigned"
            guest.save()

            AssignSlot.objects.create(
                inspector=inspector,
                guest_car=guest,
                inspection_date=inspection_date,
                inspection_time=inspection_time,
                assigned_by="inspector",
            )

            return Response({
                "message": "Slot assigned successfully",
                "assigned_to": "guest",
                "slot_date": inspection_date,
                "slot_time": inspection_time,
                "inspector": inspector.username,
                "guest_car": GuestSerializer(guest).data
            }, status=201)

        except Guest.DoesNotExist:
            return Response({"error": "Invalid guest car ID."}, status=400)
        

# INSPECTOR POST INSPECTION REPORT
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def post_inspection_report(request):
    user = request.user
    if user.role != "inspector":
        return Response(
            {"message": "Only inspectors can submit inspection reports."},
            status=status.HTTP_403_FORBIDDEN,
        )

    data = request.data
    # Get the saler_car ID from request
    saler_car_id = data.get("saler_car")
    if not saler_car_id:
        return Response(
            {"message": "Missing 'saler_car' field in request."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        car = saler_car_details.objects.get(saler_car_id=saler_car_id)
    except saler_car_details.DoesNotExist:
        return Response(
            {"message": "Car not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = InspectionReportSerializer(data=data)
    if serializer.is_valid():
        report = serializer.save(inspector=user, saler_car=car)

        Notification.objects.create(
            recipient=car.user,
            message=f"Your car '{car.car_name} ({car.year})' has been inspected by {user.username}.",
            category="Your_car_inspected",
            saler_car=car,
        )

        dealers = User.objects.filter(role="dealer")
        for dealer in dealers:
            Notification.objects.create(
                recipient=dealer,
                message=f"The car '{car.car_name} ({car.year})' has been inspected. Check the inspection report.",
                category="dealer_car_inspected",
                saler_car=car,
            )

        admins = User.objects.filter(role="admin")
        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                message=f"The car '{car.car_name} ({car.year})' has been inspected. The inspection report is available.",
                category="admin_car_inspected",
                saler_car=car,
            )

        return Response(
            {
                "message": "Inspection report submitted successfully.",
                "report": InspectionReportSerializer(report).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# manual appointment for inspector by seller and guest
@api_view(["GET"])
@permission_classes([AllowAny])
def get_assigned_slots(request):
    inspector_id = request.query_params.get("inspector_id")

    if not inspector_id:
        return Response({"error": "Inspector ID is required."}, status=400)

    try:
        inspector = User.objects.get(id=inspector_id, role="inspector")
    except User.DoesNotExist:
        return Response({"error": "Inspector not found."}, status=404)

    # Get assigned slots for saler cars
    saler_slots = AssignSlot.objects.select_related("car", "inspector").filter(
        inspector=inspector,
        car__isnull=False,
        car__status="assigned"
    ).filter(
        Q(car__user__isnull=False) | Q(car__is_manual=True)
    )

    # Get assigned slots for guest cars
    guest_slots = AssignSlot.objects.select_related("guest_car", "inspector").filter(
        inspector=inspector,
        guest_car__isnull=False,
        guest_car__status="assigned"
    )

    # Serialize both separately
    saler_serializer = AssignedSlotSerializer(saler_slots, many=True)
    guest_serializer = AssignedSlotSerializer(guest_slots, many=True)

    return Response({
        "saler_cars": saler_serializer.data,
        "guest_cars": guest_serializer.data
    }, status=200)

#manual entries for inspector by guest and seller
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_manual_entries_for_inspector(request):
    inspector_id = request.query_params.get("inspector_id")

    if not inspector_id:
        return Response({"error": "inspector_id is required."}, status=400)

    try:
        inspector = User.objects.get(id=inspector_id, role="inspector")
    except User.DoesNotExist:
        return Response({"error": "Inspector not found."}, status=404)

    manual_saler_cars = saler_car_details.objects.filter(
        is_manual=True,
        status="pending",
        inspector=inspector
    )

    manual_guests = Guest.objects.filter(
        is_manual=True,
        status="pending",
        inspector_id=inspector.id
    )

    saler_serializer = SalerCarDetailsSerializer(manual_saler_cars, many=True)
    guest_serializer = GuestSerializer(manual_guests, many=True)

    return Response({
        "manual_saler_entries": saler_serializer.data,
        "manual_guest_entries": guest_serializer.data
    }, status=200)



# INSPECTOR POST INSPECTION REPORT mobile
# @api_view(["POST"])
# @permission_classes([IsAuthenticated])
# def post_inspection_report_mob(request):

#     user = request.user
#     if user.role != "inspector":
#         return Response(
#             {"message": "Only inspectors can submit inspection reports."},
#             status=status.HTTP_403_FORBIDDEN,
#         )

#     data = request.data
#     print("Inspection report data received From mobile app:", data)

#     # Get the saler_car ID from request
#     saler_car_id = data.get("saler_car")
#     if not saler_car_id:
#         return Response(
#             {"message": "Missing 'saler_car' field in request."},
#             status=status.HTTP_400_BAD_REQUEST,
#         )

#     try:
#         car = saler_car_details.objects.get(saler_car_id=saler_car_id)
#     except saler_car_details.DoesNotExist:
#         return Response(
#             {"message": "Car not found."},
#             status=status.HTTP_404_NOT_FOUND,
#         )
#   # "json_obj"
#     # Prepare the JSON data in the expected format
#     json_obj = data.get("json_obj")
#     mobile_data = {
#         "bodyParts": json_obj.get("bodyParts"),
#         # Add other sections from mobile data as needed
#     }

#     merge_result = merge_json(my_default_json, mobile_data)

#     # Create a copy of the data with the properly formatted json_obj
#     serializer_data = {
#         **data,
#         "json_obj": merge_result
#     }

#     serializer = InspectionReportSerializer(data=serializer_data)
#     if serializer.is_valid():
#         report = serializer.save(inspector=user, saler_car=car)

#         # Notify Seller
#         Notification.objects.create(
#             recipient=car.user,
#             message=f"Your car '{car.car_name} ({car.year})' has been inspected by {user.username}.",
#             category="Your_car_inspected",
#             saler_car=car,
#         )

#         # Notify Dealers and Admins (keep your existing code)
#         # ...

#         return Response(
#             {
#                 "message": "Inspection report submitted successfully.",
#                 "report": InspectionReportSerializer(report).data,
#             },
#             status=status.HTTP_201_CREATED,
#         )

#     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def post_inspection_report_mob(request):
    user = request.user
    if user.role != "inspector":
        return Response(
            {"message": "Only inspectors can submit inspection reports."},
            status=status.HTTP_403_FORBIDDEN,
        )
    data = request.data
    saler_car_id = data.get("saler_car")
    if not saler_car_id:
        return Response(
            {"message": "Missing 'saler_car' field in request."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        car = saler_car_details.objects.get(saler_car_id=saler_car_id)
    except saler_car_details.DoesNotExist:
        return Response(
            {"message": "Car not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    json_obj = data.get("json_obj")
    mobile_data = {
        "basicInfo": json_obj.get("basicInfo", {}),
        "techSpecs": json_obj.get("techSpecs", {}),
        "bodyParts": json_obj.get("bodyParts", []),
    }
    merge_result = merge_json(my_default_json, mobile_data)
    serializer_data = {**data, "json_obj": merge_result}
    serializer = InspectionReportSerializer(data=serializer_data)
    if serializer.is_valid():
        report = serializer.save(inspector=user, saler_car=car)
        Notification.objects.create(
            recipient=car.user,
            message=f"Your car '{car.car_name} ({car.year})' has been inspected by {user.username}.",
            category="Your_car_inspected",
            saler_car=car,
        )
        Notification.objects.create(
            recipient=car.user,
            message=f"car '{car.car_name} ({car.year})' has been inspected by {user.username}.",
            category="dealer_car_inspected",
            saler_car=car,
        )
        Notification.objects.create(
            recipient=car.user,
            message=f"car '{car.car_name} ({car.year})' has been inspected by {user.username}.",
            category="admin_car_inspected",
            saler_car=car,
        )
        return Response(
            {
                "message": "Inspection report submitted successfully.",
                "report": InspectionReportSerializer(report).data,
            },
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# UPDATE INSPECTION REPORT
@permission_classes([IsAuthenticated])
@api_view(["PUT"])
def update_inspection_report(request, report_id):
    user = request.user
    if user.role != "inspector":
        return Response(
            {"message": "only inspector can update"}, status=status.HTTP_403_FORBIDDEN
        )

    try:
        report = InspectionReport.objects.get(id=report_id, inspector=user)
        print(f"Report found: {report}")
    except InspectionReport.DoesNotExist:
        # Debugging line
        print(f"Report with ID {report_id} not found for inspector {user}")
        return Response(
            {"message": "Report not found"}, status=status.HTTP_404_NOT_FOUND
        )

    data = request.data

    car_photos = data.get("car_photos", [])
    decoded_photos = []
    for index, photo in enumerate(car_photos):
        try:
            format, imgstr = photo.split(";base64,")
            ext = format.split("/")[-1]
            decoded_photos.append(f"data:image/{ext};base64,{imgstr}")
        except Exception as e:
            return Response(
                {"message": f"Error processing image: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    report.car_name = data.get("car_name", report.car_name)
    report.company = data.get("company", report.company)
    report.color = data.get("color", report.color)
    report.condition = data.get("condition", report.condition)
    report.model = data.get("model", report.model)
    report.fuel_type = data.get("fuel_type", report.fuel_type)
    report.year = data.get("year", report.year)
    report.engine_capacity = data.get("engine_capacity", report.engine_capacity)
    report.mileage = data.get("mileage", report.mileage)
    report.engine_type = data.get("engine_type", report.engine_type)
    report.transmission_type = data.get("transmission_type", report.transmission_type)

    report.engine_condition = data.get("engine_condition", report.engine_condition)
    report.body_condition = data.get("body_condition", report.body_condition)
    report.clutch_condition = data.get("clutch_condition", report.clutch_condition)
    report.steering_condition = data.get(
        "steering_condition", report.steering_condition
    )
    report.suspension_condition = data.get(
        "suspension_condition", report.suspension_condition
    )
    report.brakes_condition = data.get("brakes_condition", report.brakes_condition)
    report.ac_condition = data.get("ac_condition", report.ac_condition)
    report.tyres_condition = data.get("tyres_condition", report.tyres_condition)
    report.electrical_condition = data.get(
        "electrical_condition", report.electrical_condition
    )

    report.estimated_value = data.get("estimated_value", report.estimated_value)
    report.saler_demand = data.get("saler_demand", report.saler_demand)

    report.additional_comments = data.get(
        "additional_comments", report.additional_comments
    )
    report.car_photos = decoded_photos if decoded_photos else report.car_photos

    condition_fields = [
        report.engine_condition,
        report.body_condition,
        report.clutch_condition,
        report.steering_condition,
        report.suspension_condition,
        report.brakes_condition,
        report.ac_condition,
        report.electrical_condition,
        report.tyres_condition,
    ]
    report.overall_score = sum(condition_fields) / len(condition_fields)

    report.save()

    # Send Notifications
    try:
        if report.saler_car.user:
            Notification.objects.create(
                recipient=report.saler_car.user,
                message=f"Your car '{report.saler_car.car_name}' inspection report has been updated.",
                category="inspection_updated",
                saler_car=report.saler_car,
            )

        dealers = User.objects.filter(role="dealer")
        for dealer in dealers:
            Notification.objects.create(
                recipient=dealer,
                message=f"Updated inspection report available for '{report.saler_car.car_name}'.",
                category="dealer_inspection_updated",
                saler_car=report.saler_car,
            )

        admins = User.objects.filter(role="admin")
        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                message=f"Inspection report updated for '{report.saler_car.car_name}'.",
                category="admin_inspection_updated",
                saler_car=report.saler_car,
            )

    except Exception as e:
        logger.error(f"Error while creating notifications: {str(e)}")

    serialized_report = InspectionReportSerializer(report)
    return Response(
        {
            "message": "Inspection report updated successfully",
            "report": serialized_report.data,
        },
        status=status.HTTP_200_OK,
    )


# INSPECTOR MAKE SCHEDULE//////////////////
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_availability(request):
    user = request.user

    if user.role.lower() != "inspector":
        return Response(
            {"message": "Only an inspector can add availability."}, status=403
        )

    data = request.data
    date_slots = data.get("dateSlots")

    if not date_slots or not isinstance(date_slots, list):
        return Response(
            {"message": "A list of date and slot pairs is required."}, status=400
        )
    try:
        for entry in date_slots:
            date_str = entry.get("date")
            slots = entry.get("slots")

            if not date_str or not slots or not isinstance(slots, list):
                return Response(
                    {
                        "message": "Each entry must have a valid 'date' and a list of 'slots'."
                    },
                    status=400,
                )

            try:
                current_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"message": f"Invalid date format: {date_str}. Use YYYY-MM-DD."},
                    status=400,
                )

            if current_date < localtime(now()).date():
                return Response(
                    {"message": "Cannot add slots for past dates."}, status=400
                )

            valid_slots = set()
            for slot in slots:
                try:
                    parsed_time = datetime.strptime(slot.strip(), "%I:%M %p")
                    formatted_slot = parsed_time.strftime("%I:%M %p")
                    valid_slots.add(formatted_slot)
                except ValueError:
                    return Response(
                        {
                            "message": f"Invalid time format: {slot}. Use 12-hour format (e.g., 2:30 PM)."
                        },
                        status=400,
                    )

            availability, _ = Availability.objects.get_or_create(
                inspector=user, date=current_date
            )

            existing_slots = set(availability.time_slots or [])
            updated_slots = list(existing_slots.union(valid_slots))

            availability.time_slots = sorted(updated_slots)
            availability.save()

        return Response(
            {"message": "Availability slots added successfully."}, status=201
        )

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return Response(
            {"message": "An unexpected error occurred. Please try again later."},
            status=500,
        )


# when seller select slot
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_seller_appointment_notification(request):
    user = request.user
    appointment_notifications = Notification.objects.filter(
        recipient=user, category="seller_time_slot_selection"
    ).order_by("-created_at")

    serializer = NotificationSerializer(appointment_notifications, many=True)

    return Response(serializer.data, status=status.HTTP_200_OK)


# @api_view(["GET"])
# @permission_classes([AllowAny])
# def get_free_slots(request):
#     try:
#         date = request.query_params.get("date", None)
#         inspector_id = request.query_params.get("inspector", None)

#         if not inspector_id:
#             return Response(
#                 {"message": "Inspector ID is required."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         if date:
#             try:
#                 date_obj = datetime.strptime(date, "%Y-%m-%d").date()
#             except ValueError:
#                 return Response(
#                     {"message": "Invalid date format. Use YYYY-MM-DD."},
#                     status=status.HTTP_400_BAD_REQUEST,
#                 )
#         else:
#             date_obj = None

#         availability_queryset = Availability.objects.filter(inspector_id=inspector_id)
#         if date_obj:
#             availability_queryset = availability_queryset.filter(date=date_obj)

#         if not availability_queryset.exists():
#             return Response(
#                 {
#                     "message": "No availability records found for the given inspector and date."
#                 },
#                 status=status.HTTP_404_NOT_FOUND,
#             )

#         reserved_slots_queryset = SelectedSlot.objects.filter(inspector_id=inspector_id)
#         if date_obj:
#             reserved_slots_queryset = reserved_slots_queryset.filter(date=date_obj)

#         car_inspections = saler_car_details.objects.filter(inspector__id=inspector_id)
#         if date_obj:
#             car_inspections = car_inspections.filter(inspection_date=date_obj)

#         taken_slots = set()
#         unique_reserved_slots = {}

#         for slot in reserved_slots_queryset:
#             time_str = slot.time_slot.strftime("%I:%M %p")
#             taken_slots.add(time_str)

#             key = (slot.date, slot.inspector, time_str)
#             if key not in unique_reserved_slots:
#                 unique_reserved_slots[key] = {
#                     "source": "manual",
#                     "slot_id": slot.id,
#                     "date": slot.date.strftime("%Y-%m-%d"),
#                     "inspector": slot.inspector.username,
#                     "time_slot": time_str,
#                 }

#         for car in car_inspections:
#             if car.inspection_time:
#                 try:
#                     time_obj = datetime.strptime(car.inspection_time, "%I:%M %p").time()
#                 except ValueError:
#                     time_obj = datetime.strptime(car.inspection_time, "%H:%M").time()

#                 time_str = time_obj.strftime("%I:%M %p")
#                 taken_slots.add(time_str)

#                 key = (car.inspection_date, car.inspector, time_str)
#                 if key not in unique_reserved_slots:
#                     unique_reserved_slots[key] = {
#                         "slot_id": car.saler_car_id,
#                         "date": car.inspection_date.strftime("%Y-%m-%d"),
#                         "inspector": car.inspector.username if car.inspector else "",
#                         "time_slot": time_str,
#                         "car_name": car.car_name,
#                         "status": car.status,
#                     }

#         reserved_slots = list(unique_reserved_slots.values())

#         free_slots = []
#         for availability in availability_queryset:
#             available_time_slots = availability.time_slots
#             available_free_slots = [
#                 slot for slot in available_time_slots if slot not in taken_slots
#             ]

#             for slot in available_free_slots:
#                 free_slots.append(
#                     {
#                         "availability_id": availability.id,
#                         "date": availability.date.strftime("%Y-%m-%d"),
#                         "inspector": availability.inspector.username,
#                         "time_slot": slot,
#                     }
#                 )
#         return Response(
#             {
#                 "message": "Fetched slots successfully",
#                 "free_slots": free_slots,
#                 "reserved_slots": reserved_slots,
#             },
#             status=status.HTTP_200_OK,
#         )
#     except Exception as e:
#         return Response(
#             {"message": f"An unexpected error occurred: {str(e)}"},
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#         )

@api_view(["GET"])
@permission_classes([AllowAny])
def get_free_slots(request):
    try:
        date = request.query_params.get("date", None)
        inspector_id = request.query_params.get("inspector", None)

        if not inspector_id:
            return Response(
                {"message": "Inspector ID is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"message": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            date_obj = None

        now = datetime.now()
        current_time = now.time()
        current_date = now.date()

        availability_queryset = Availability.objects.filter(inspector_id=inspector_id)
        if date_obj:
            availability_queryset = availability_queryset.filter(date=date_obj)

        if not availability_queryset.exists():
            return Response(
                {"message": "No availability records found for the given inspector and date."},
                status=status.HTTP_404_NOT_FOUND,
            )

        reserved_slots_queryset = SelectedSlot.objects.filter(inspector_id=inspector_id)
        if date_obj:
            reserved_slots_queryset = reserved_slots_queryset.filter(date=date_obj)

        car_inspections = saler_car_details.objects.filter(inspector__id=inspector_id)
        if date_obj:
            car_inspections = car_inspections.filter(inspection_date=date_obj)

        taken_slots = set()
        reserved_slots = []
        passed_slots = []

        for slot in reserved_slots_queryset:
            time_str = slot.time_slot.strftime("%I:%M %p")
            taken_slots.add(time_str)

            slot_data = {      
                "slot_id": slot.id,
                "date": slot.date.strftime("%Y-%m-%d"),
                # "inspector": slot.inspector.username,
                "time_slot": time_str,
            }
            reserved_slots.append(slot_data)

            if slot.date < current_date or (slot.date == current_date and slot.time_slot < current_time):
                passed_slots.append(slot_data)

        for car in car_inspections:
            if car.inspection_time:
                try:
                    time_obj = datetime.strptime(car.inspection_time, "%I:%M %p").time()
                except ValueError:
                    time_obj = datetime.strptime(car.inspection_time, "%H:%M").time()

                time_str = time_obj.strftime("%I:%M %p")
                taken_slots.add(time_str)

                slot_data = {
                    "slot_id": car.saler_car_id,
                    "date": car.inspection_date.strftime("%Y-%m-%d"),
                    "time_slot": time_str,
                    # "car_name": car.car_name,
                    # "status": car.status,
                }
                reserved_slots.append(slot_data)
                
                if car.inspection_date < current_date or (car.inspection_date == current_date and time_obj < current_time):
                    passed_slots.append(slot_data)

        free_slots = []
        passed_free_slots = []
        
        for availability in availability_queryset:
            for slot_str in availability.time_slots:
                if slot_str not in taken_slots:
                    try:
                        slot_time = datetime.strptime(slot_str, "%I:%M %p").time()
                    except ValueError:
                        slot_time = datetime.strptime(slot_str, "%H:%M").time()
                    
                    slot_data = {
                        "availability_id": availability.id,
                        "date": availability.date.strftime("%Y-%m-%d"),
                        "inspector": availability.inspector.username,
                        "time_slot": slot_str,
                    }

                    if availability.date < current_date or (availability.date == current_date and slot_time < current_time):
                        passed_free_slots.append(slot_data)
                    else:
                        free_slots.append(slot_data)

        return Response(
            {
                "message": "Fetched slots successfully",
                "free_slots": free_slots,
                "reserved_slots": reserved_slots,
                "passed_slots": passed_slots + passed_free_slots 
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response(
            {"message": f"An unexpected error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

# GET ALL SLOTS -----NOT USED
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_available_slot(request):
    date = request.query_params.get("date")
    inspector_id = request.query_params.get("inspector")
    filters = {}
    if date:
        filters["date"] = date
    if inspector_id:
        filters["inspector_id"] = inspector_id

    availabilites = Availability.objects.filter(**filters)
    serializer = AvailabilitySerializer(availabilites, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notifications_as_read(request):
    user = request.user
    Notification.objects.filter(recipient=user, is_read=False).update(is_read=True)
    return Response(
        {"message": "Notifications marked as read"}, status=status.HTTP_200_OK
    )


# GET SELECTED SLOT
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_selected_slots(request):
    user = request.user
    selected_slots = SelectedSlot.objects.filter(saler_car__user=user)
    serialized_slots = SelectedSlotSerializer(selected_slots, many=True)

    return Response(
        {
            "message": "Fetched selected slots successfully",
            "slots": serialized_slots.data,
        },
        status=status.HTTP_200_OK,
    )


# all notification get according to role
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    user = request.user

    if user.role == "saler":
        notifications = Notification.objects.filter(
            recipient=user,
            category__in=["Your_car_inspected", "car_approved","car_rejected","car_sold"],
            saler_car__user=user,
            is_read=False
        )
    elif user.role == "dealer":
        notifications = Notification.objects.filter(
            recipient=user,
            category__in=["dealer_car_inspected", "dealer_new_bid_car","dealer_guest_car_approved"],
            is_read=False
        )
    
    elif user.role == "inspector":
        notifications = Notification.objects.filter(
            recipient=user,
            category__in=["saler_car_details", "inspection_assignment"],
            is_read=False
        )
    
    elif user.role == "admin":
        notifications = Notification.objects.filter(
            recipient=user,
            category__in=["admin_car_inspected", "admin_guest_car_inspected"],
            is_read=False
        )
    else:
        return Response(
            {"message": "No notifications for this role"},
            status=status.HTTP_403_FORBIDDEN,
        )
    serializer = NotificationSerializer(notifications, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# GET INSPECTION REPORT
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_inspection_report(request):
    car_id = request.GET.get("car_id")
    if not car_id:
        return Response(
            {"message": "Provide Car ID"}, status=status.HTTP_400_BAD_REQUEST
        )
    try:
        report = InspectionReport.objects.get(saler_car=car_id)
        serializer = InspectionReportSerializer(report)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except InspectionReport.DoesNotExist:
        return Response(
            {"message": "No report found for this car"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:  # type: ignore
        report = InspectionReport.objects.filter(saler_car=car_id).first()
        serializer = InspectionReportSerializer(report)
        return Response(serializer.data, status=status.HTTP_200_OK)


# @api_view(["GET"])
# @permission_classes([IsAuthenticated])
# def get_inspection_report(request):
#     car_id = request.GET.get("car_id")

#     if not car_id:
#         return Response(
#             {"message": "Provide Car ID"}, status=status.HTTP_400_BAD_REQUEST
#         )

#     reports = InspectionReport.objects.select_related("saler_car__user").filter(
#         saler_car=car_id
#     )

#     if not reports.exists():
#         return Response(
#             {"message": "No report found for this car"},
#             status=status.HTTP_404_NOT_FOUND,
#         )

#     serialized_reports = InspectionReportSerializer(reports, many=True)

#     return Response(serialized_reports.data, status=status.HTTP_200_OK)


# get list of guest cars to show to inspector
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_guest_car_details(request):
    try:
        inspector_id = request.GET.get("inspector_id")

        if not inspector_id:
            return Response(
                {"error": "Inspector ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            inspector = User.objects.get(id=inspector_id, role__iexact="Inspector")
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid inspector ID"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Removed .select_related("guest") because 'guest' is not a foreign key
        assigned_cars = Guest.objects.filter(
            inspector=inspector, status="pending", is_manual=False
        )

        serializer = GuestSerializer(assigned_cars, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Error in get_guest_car_details: {e}")
        return Response(
            {"success": False, "message": f"Error retrieving assigned cars: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ///////////////////////////DEALERS APIs/////////////////////////


# bidding cars status for dealer and admin
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_bidding_cars(request):
    user = request.user

    if user.role not in ["dealer", "admin"]:
        return Response(
            {"message": "Only dealers or admins can view this"},
            status=status.HTTP_403_FORBIDDEN,
        )
    cars = saler_car_details.objects.select_related("user").filter(status="bidding")

    if not cars.exists():
        return Response(
            {"error": "No cars found in bidding status"},
            status=status.HTTP_404_NOT_FOUND,
        )
    serializer = SalerCarDetailsSerializer(cars, many=True)

    return Response(
        {"message": "Cars fetched successfully", "cars": serializer.data},
        status=status.HTTP_200_OK,
    )


# get cars with status inspection for dealer and admin (upcoming)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_upcoming_cars(request):
    cars = saler_car_details.objects.filter(
        Q(status="pending") | Q(status="in_inspection") | Q(status="await_approval")
    )
    if not cars.exists():
        return Response(
            {"Message": "No Upcoming cars Found!"}, status=status.HTTP_404_NOT_FOUND
        )
    serializer = SalerCarDetailsSerializer(cars, many=True)

    return Response({"cars": serializer.data}, status=status.HTTP_200_OK)


# DEALERS CAN PLACE BID
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def place_bid(request):
    user = request.user

    if user.role != "dealer":
        return Response(
            {"message": "Only dealers can place bids"}, status=status.HTTP_403_FORBIDDEN
        )

    data = request.data
    saler_car_id = data.get("saler_car")
    guest_car_id = data.get("guest_car")
    bid_amount = data.get("bid_amount")

    if not bid_amount or (not saler_car_id and not guest_car_id):
        return Response(
            {"message": "bid_amount and either saler_car or guest_car are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    bid = None
    saler_car = None
    guest_car = None

    # Handle saler_car bidding
    if saler_car_id:
        try:
            saler_car = saler_car_details.objects.get(saler_car_id=saler_car_id)
        except saler_car_details.DoesNotExist:
            return Response({"message": "Saler car not found"}, status=status.HTTP_404_NOT_FOUND)

        if saler_car.is_sold:
            return Response({"message": "This saler car is already sold"}, status=status.HTTP_400_BAD_REQUEST)

        bid = Bidding.objects.create(
            dealer=user, saler_car=saler_car, bid_amount=bid_amount
        )

    # Handle guest_car bidding
    elif guest_car_id:
        try:
            guest_car = Guest.objects.get(id=guest_car_id)
        except Guest.DoesNotExist:
            return Response({"message": "Guest car not found"}, status=status.HTTP_404_NOT_FOUND)

        if guest_car.is_sold:
            return Response({"message": "This guest car is already sold"}, status=status.HTTP_400_BAD_REQUEST)

        bid = Bidding.objects.create(
            dealer=user, guest_car=guest_car, bid_amount=bid_amount
        )

    # Notify admins
    User = get_user_model()
    admin_users = User.objects.filter(role="admin")
    for admin in admin_users:
        if saler_car:
            message = f"A new bid of {bid_amount} has been placed on {saler_car.company} {saler_car.car_name}"
        else:
            message = f"A new bid of {bid_amount} has been placed on {guest_car.company} {guest_car.car_name}"

        Notification.objects.create(
            recipient=admin,
            message=message,
            saler_car=saler_car,
            guest_car=guest_car,
            category="new_bid",
            bid=bid,
        )

    serializer = BiddingSerializer(bid)
    return Response(
        {"message": "Bid placed successfully", "bid_id": bid.id, "bid": serializer.data},
        status=status.HTTP_201_CREATED,
    )




# @api_view(["POST"])
# @permission_classes([IsAuthenticated])
# def place_bid(request):
#     user = request.user

#     if user.role != "dealer":
#         return Response(
#             {"message": "Only dealers can place bids"}, status=status.HTTP_403_FORBIDDEN
#         )
#     data = request.data
#     try:
#         saler_car = saler_car_details.objects.get(saler_car_id=data["saler_car"])
#     except saler_car_details.DoesNotExist:
#         return Response({"message": "Car not found"}, status=status.HTTP_404_NOT_FOUND)

#     if saler_car.is_sold:
#         return Response(
#             {"message": "This car is already sold"}, status=status.HTTP_400_BAD_REQUEST
#         )
#     bid = Bidding.objects.create(
#         dealer=user, saler_car=saler_car, bid_amount=data["bid_amount"]
#     )
#     User = get_user_model()
#     admin_users = User.objects.filter(role="admin")
#     for admin in admin_users:
#         Notification.objects.create(
#             recipient=admin,
#             message=f"A new bid of {data['bid_amount']} has been placed on {saler_car.company} {saler_car.car_name}",
#             saler_car=saler_car,
#             category="new_bid",
#             bid=bid,
#         )
#     serializer = BiddingSerializer(bid)
#     return Response(
#         {
#             "message": "Bid placed successfully",
#             "bid_id": bid.id,
#             "bid": serializer.data,
#         },
#         status=status.HTTP_201_CREATED,
#     )


# DEALER CAN VIEW THEIR OWN BIDS
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def view_dealer_bids(request):
    user = request.user

    if user.role != "dealer":
        return Response(
            {"Message": "Onlt dealer can view their Bids"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    bids = Bidding.objects.filter(dealer=user).order_by("-bid_date")
    serializer = BiddingSerializer(bids, many=True)

    return Response(
        {"Message": "successfuly fetched", "bids": serializer.data},
        status=status.HTTP_200_OK,
    )


# dealer inventory API
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dealer_inventory(request):
    user = request.user
    if user.role != "dealer":
        return Response(
            {"message": "unauthorized cannot access this resource"},
            status=status.HTTP_403_FORBIDDEN,
        )
    cars = saler_car_details.objects.filter(winner_dealer=user)
    guest = Guest.objects.filter(winner_dealer=user)
    

    seller_cars = SalerCarDetailsSerializer(cars, many=True)
    guest_cars = GuestSerializer(guest,many=True)
    
    return Response(
        {"message": "success", 
         "seller_cars": seller_cars.data,
         "guest_cars" : guest_cars.data,
         }, status=status.HTTP_200_OK
    )


# ///////////////////////////////////GUEST APIs////////////////////////////////////////////

# GUEST ADD ITS BASIC DETAILS


# @api_view(["POST"])
# @permission_classes([AllowAny])
# def post_guest_details(request):
#     serializer = GuestSerializer(data=request.data)
#     print(request.data)

#     if serializer.is_valid():
#         guest = serializer.save()
#         return Response(
#             {"Message": "Data saved", "guest_id": guest.id, "data": serializer.data},
#             status=status.HTTP_201_CREATED,
#         )

#     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# GUEST POST CAR FOR SALE
# @api_view(["POST"])
# @permission_classes([AllowAny])
# def guest_add_car_details(request):
#     try:
#         data = request.data.copy()
#         data["added_by"] = "guest"

#         guest_id = data.get("guest_id")
#         if not guest_id:
#             return Response(
#                 {"error": "Guest ID is required."}, status=status.HTTP_400_BAD_REQUEST
#             )

#         try:
#             guest = Guest.objects.get(id=guest_id)
#         except Guest.DoesNotExist:
#             return Response(
#                 {"error": "Invalid Guest ID."}, status=status.HTTP_400_BAD_REQUEST
#             )

#         data.pop("guest_id", None)
#         serializer = SalerCarDetailsSerializer(data=data)
#         if serializer.is_valid():
#             car_details = serializer.save(guest=guest)

#             return Response(
#                 {
#                     "message": "Car added successfully!",
#                     "car_id": car_details.saler_car_id,
#                 },
#                 status=status.HTTP_201_CREATED,
#             )

#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     except Exception as e:
#         print(f"Error in guest_add_car_details view: {str(e)}")
#         return Response(
#             {"success": False, "message": "An error occurred while adding car details"},
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#         )


# GUEST POST AD
@api_view(["POST"])
@permission_classes([AllowAny])
def guest_add_car_details(request):
    try:
        data = request.data.copy()
        data["added_by"] = "guest"

        inspector_id = data.get("inspector_id")
        inspector = None

        if inspector_id:
            try:
                inspector = User.objects.get(id=inspector_id, role="inspector")
                data["inspector"] = inspector.id
            except User.DoesNotExist:
                return Response(
                    {"error": "Invalid Inspector ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        guest_serializer = GuestSerializer(data=data)
        if guest_serializer.is_valid():
            guest = guest_serializer.save()

            # Save selected slot if both values are present
            if inspector and guest.inspection_time and guest.inspection_date:
                try:
                    parsed_time = datetime.strptime(
                        guest.inspection_time.strip(), "%I:%M %p"
                    ).time()
                except ValueError:
                    return Response(
                        {
                            "error": "Invalid inspection_time format. Use 12-hour format (e.g., 02:30 PM)."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                SelectedSlot.objects.create(
                    inspector=inspector,
                    date=guest.inspection_date,
                    time_slot=parsed_time,
                    unreg_guest=guest,
                    booked_by="guest",
                )

            # Notification formatting
            if inspector:
                inspection_date = guest.inspection_date
                inspection_time = guest.inspection_time

                message = (
                    f"You have been assigned to inspect the car '{guest.car_name}' "
                    f"from guest '{guest.name}'. "
                )

                if inspection_date and inspection_time:
                    message += f"Appointment scheduled on {inspection_date} at {inspection_time}."
                else:
                    message += "No appointment scheduled."

                Notification.objects.create(
                    recipient=inspector,
                    message=message,
                    category="inspection_assignment",
                )

            return Response(
                {
                    "message": "Guest and car details submitted successfully.",
                    "data": guest_serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(guest_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        print(f"Error in guest_add_car_details view: {str(e)}")
        return Response(
            {
                "success": False,
                "message": f"An error occurred while saving guest details: {str(e)}",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

# assigning inspector to guest car for manual entry
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def assign_inspector_to_guest_car(request):
    try:

        guest_id = request.data.get("unreg_guest_id")
        inspector_id = request.data.get("inspector_id")

        if not guest_id or not inspector_id:
            return Response(
                {"error": "Guest ID and Inspector ID are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            inspector = User.objects.get(id=inspector_id, role="inspector")
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid inspector selected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            guest = Guest.objects.get(id=guest_id)
        except Guest.DoesNotExist:
            return Response(
                {"error": "Guest record not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        guest.inspector = inspector
        guest.is_manual = (True,)
        guest.save()

        return Response(
            {"message": "Inspector assigned to guest successfully!"},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        print(f"Error in assign_inspector_to_guest_car: {e}")
        return Response(
            {"success": False, "message": f"An error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# get cars of guest for inspector as inspector appointment
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_inspector_appointmnet_by_guest(request):
    try:
        inspector_id = request.query_params.get("inspector_id")

        if not inspector_id:
            return Response(
                {"error": "Inspector ID is required as a query parameter."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            inspector = User.objects.get(id=inspector_id, role="inspector")
        except User.DoesNotExist:
            return Response(
                {"error": "Inspector not found or invalid role."},
                status=status.HTTP_404_NOT_FOUND,
            )

        guest_cars = Guest.objects.filter(inspector_id=inspector.id, is_manual=False)

        serializer = GuestSerializer(guest_cars, many=True)
        return Response(
            {
                "inspector": {
                    "id": inspector.id,
                    "name": inspector.get_full_name() or inspector.username,
                    "email": inspector.email,
                },
                "guest_cars": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": f"An error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# GUest manual entries for inspector not used
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_manual_guest_cars_for_inspector(request, inspector_id):
    try:
        try:
            inspector = User.objects.get(id=inspector_id, role="inspector")
        except User.DoesNotExist:
            return Response(
                {"error": "Inspector not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        guests = Guest.objects.filter(inspector_id=inspector.id, is_manual=True)

        serializer = GuestSerializer(guests, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        print(f"Error in get_manual_guest_cars_for_inspector: {e}")
        return Response(
            {"success": False, "message": "An error occurred."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ASSIGN SLOT TO GUEST
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def assign_guest_slot(request):
    data = request.data.copy()

    required_fields = ["guest_id", "inspection_date", "inspection_time"]
    for field in required_fields:
        if field not in data:
            return Response(
                {"error": f"{field.replace('_', ' ').capitalize()} is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    try:
        guest = Guest.objects.get(id=data["guest_id"])
    except Guest.DoesNotExist:
        return Response({"error": "Guest not found."}, status=status.HTTP_404_NOT_FOUND)
    input_time = data.get("inspection_time")
    try:
        parsed_time = datetime.strptime(input_time.strip(), "%I:%M %p")
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid time format. Use 12-hour format like '01:30 PM'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    guest.inspector = request.user
    guest.inspection_date = data["inspection_date"]
    guest.inspection_time = parsed_time.strftime("%I:%M %p")
    guest.is_manual = True
    guest.status = "assigned"
    guest.save()

    try:
        availability = Availability.objects.get(
            inspector=request.user, date=data["inspection_date"]
        )
        availability.time_slots = [
            slot.strftime("%I:%M %p") if isinstance(slot, datetime) else slot
            for slot in availability.time_slots
        ]
        if guest.inspection_time in availability.time_slots:
            availability.time_slots.remove(guest.inspection_time)
            availability.save(update_fields=["time_slots"])
    except Availability.DoesNotExist:
        return Response(
            {"error": "Availability record not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {
            "message": "Guest slot assigned successfully.",
            "guest_id": guest.id,
            "inspector": {
                "id": request.user.id,
                "name": request.user.get_full_name() or request.user.username,
                "email": request.user.email,
            },
            "inspection_date": guest.inspection_date,
            "inspection_time": guest.inspection_time,
        },
        status=status.HTTP_200_OK,
    )


# GUEST: is_inspected sets true
@api_view(["POST"])
@permission_classes([AllowAny])
def mark_guest_car_as_inspected(request, id):
    guest = get_object_or_404(Guest, id=id)
    guest.is_inspected = True
    guest.save()
    return Response(
        {"message": "Car marked as inspected", "is_inspected": guest.is_inspected}
    )


# @api_view(["POST"])
# @permission_classes([IsAuthenticated])
# def post_guest_inspection_report(request):
#     user = request.user
#     if user.role != "inspector":
#         return Response(
#             {"message": "Only inspectors can submit inspection reports."},
#             status=status.HTTP_403_FORBIDDEN,
#         )

#     data = request.data
#     guest_id = data.get("guest_id")
#     if not guest_id:
#         return Response(
#             {"message": "Missing 'guest_id' field in request."},
#             status=status.HTTP_400_BAD_REQUEST,
#         )

#     try:
#         guest = Guest.objects.get(id=guest_id)
#     except Guest.DoesNotExist:
#         return Response(
#             {"message": "Guest not found."},
#             status=status.HTTP_404_NOT_FOUND,
#         )

#     serializer = InspectionReportSerializer(data=data)
#     if serializer.is_valid():
#         report = serializer.save(inspector=user, guest_car=guest)

#         Notification.objects.create(
#             recipient=guest.user,  # If Guest has user field
#             message=f"Your car '{guest.car_model}' has been inspected by {user.username}.",
#             category="guest_car_inspected",
#         )

#         return Response(
#             {
#                 "message": "Guest car inspection report submitted successfully.",
#                 "report": InspectionReportSerializer(report).data,
#             },
#             status=status.HTTP_201_CREATED,
#         )

#     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# inspector post inspection report of guest cars
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def guest_inspection_report_post(request):
    user = request.user
    if user.role != "inspector":
        return Response(
            {"message": "only inspector can post"}, status=status.HTTP_403_FORBIDDEN
        )

    data = request.data

    guest_car_id = data.get("guest_car")

    if not guest_car_id:
        return Response(
            {"message": "missing guest car in fields"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        car = Guest.objects.get(id=guest_car_id)
    except Guest.DoesNotExist:
        return Response({"message": "not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = InspectionReportSerializer(data=data)

    if serializer.is_valid():
        report = serializer.save(inspector=user, guest_car=car)

        return Response(
            {
                "message": "inspection report submitted successfully",
                "report": InspectionReportSerializer(report).data,
            },
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def post_guest_inspection_report_mob(request):
    user = request.user
    if user.role != "inspector":
        return Response(
            {"message": "Only inspectors can submit inspection reports."},
            status=status.HTTP_403_FORBIDDEN,
        )

    data = request.data
    guest_car_id = data.get("guest_car")
    if not guest_car_id:
        return Response(
            {"message": "Missing 'guest_car' field in request."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        car = Guest.objects.get(id=guest_car_id)
    except Guest.DoesNotExist:
        return Response(
            {"message": "Guest car not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    json_obj = data.get("json_obj")
    mobile_data = {
        "basicInfo": json_obj.get("basicInfo", {}),
        "techSpecs": json_obj.get("techSpecs", {}),
        "bodyParts": json_obj.get("bodyParts", []),
    }

    merge_result = merge_json(my_default_json, mobile_data)

    serializer_data = {**data, "json_obj": merge_result}

    serializer = InspectionReportSerializer(data=serializer_data)
    if serializer.is_valid():
        report = serializer.save(inspector=user, guest_car=car)

        # Optional Notification if guest user exists (enable only if needed)
        # if car.user:
        #     Notification.objects.create(
        #         recipient=car.user,
        #         message=f"Your guest car '{car.car_model}' has been inspected by {user.username}.",
        #         category="guest_car_inspected",
        #         guest_car=car,
        #     )
        
                # Notify admins
        admins = User.objects.filter(role="admin")
        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                message=f"Guest car '{car.car_name} ({car.year})' has been inspected. Check the inspection report.",
                category="admin_guest_car_inspected",
                guest_car=car,
            )

        return Response(
            {
                "message": "Guest car inspection report submitted successfully.",
                "report": InspectionReportSerializer(report).data,
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# GET GUEST INSPECTION REPORT
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_inspection_report_guest(request):
    car_id = request.GET.get("car_id")

    if not car_id:
        return Response(
            {"message": "car id is required"}, status=status.HTTP_400_BAD_REQUEST
        )
    try:
        report = InspectionReport.objects.get(guest_car=car_id)
        serializer = InspectionReportSerializer(report)
        return Response({serializer.data}, status=status.HTTP_200_OK)
    except InspectionReport.DoesNotExist:
        return Response(
            {"message": "Report not found"}, status=status.HTTP_404_NOT_FOUND
        )

    except Exception as e:
        report = InspectionReport.objects.filter(guest_car=car_id).first()
        if report:
            serializer = InspectionReportSerializer(report)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {"message": "Unexpected error or no report found"},
            status=status.HTTP_404_NOT_FOUND,
        )


# guest car status update
@api_view(["PATCH"])
@permission_classes({IsAuthenticated})
def update_car_status(request, guest_car_id):

    try:
        guest_car = Guest.objects.get(id=guest_car_id)
        new_status = request.data.get("status")

        valid_status = dict(Guest.STATUS_CHOICES).keys()
        if new_status not in valid_status:
            return Response(
                {"message": "invalid status"}, status=status.HTTP_400_BAD_REQUEST
            )

        guest_car.status = new_status
        guest_car.save()
        return Response(
            {"message": "status updated successfully", "new_status": guest_car.status},
            status=status.HTTP_200_OK,
        )
    except Guest.DoesNotExist:
        return Response({"message": "not found"}, status=status.HTTP_404_NOT_FOUND)
    
    
# upcoming cars from guest
# get cars with status inspection for dealer and admin (upcoming)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_upcoming_cars_by_guest(request):
    cars = Guest.objects.filter(
        Q(status="pending") | Q(status="in_inspection") | Q(status="await_approval")
    )
    if not cars.exists():
        return Response(
            {"Message": "No Upcoming cars Found!"}, status=status.HTTP_404_NOT_FOUND
        )
    serializer = GuestSerializer(cars, many=True)

    return Response({"cars": serializer.data}, status=status.HTTP_200_OK)


# get live cars of guest
# bidding cars status for dealer and admin
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_bidding_cars_by_guest(request):
    user = request.user

    if user.role not in ["dealer", "admin"]:
        return Response(
            {"message": "Only dealers or admins can view this"},
            status=status.HTTP_403_FORBIDDEN,
        )

    cars = Guest.objects.filter(status="bidding")

    if not cars.exists():
        return Response(
            {"error": "No cars found in bidding status"},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = GuestSerializer(cars, many=True)
    return Response(
        {"message": "Cars fetched successfully", "cars": serializer.data},
        status=status.HTTP_200_OK,
    )
    
    
# admin Accept Guest car inspection
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approve_guest_inspection(request, report_id):
    report = get_object_or_404(InspectionReport, id=report_id)

    if report.guest_car and report.guest_car.status == "await_approval":
        report.guest_car.status = "bidding"
        report.guest_car.save()
        
        
                # Notify all dealers
        dealers = User.objects.filter(role="dealer")
        for dealer in dealers:
            Notification.objects.create(
                recipient=dealer,
                message=f"Guest car '{report.guest_car.car_name}' has been approved for bidding.",
                category="dealer_guest_car_approved",
                guest_car=report.guest_car,
            )
            
            
        return Response(
            {"message": "Guest car approved and moved to bidding"},
            status=status.HTTP_200_OK,
        )

    return Response(
        {"message": "Guest car is not in await_approval status or not linked properly"},
        status=status.HTTP_400_BAD_REQUEST,
    )




# Admin reject Guest car inspection
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reject_guest_inspection(request, report_id):
    report = get_object_or_404(InspectionReport, id=report_id)

    if report.guest_car and report.guest_car.status == "await_approval":
        report.guest_car.status = "rejected"
        report.guest_car.save()
        return Response(
            {"message": "Guest car inspection rejected"},
            status=status.HTTP_200_OK,
        )

    return Response(
        {"message": "Guest car is not in await_approval status or not linked properly"},
        status=status.HTTP_400_BAD_REQUEST,
    )



# ////////////////////////////////////////////////////////other like status updating///////////////
# get notification for inspector when seller or guest ad post
# @api_view(["GET"])
# @permission_classes([IsAuthenticated])
# def get_notifications(request):
#     user = request.user

#     notifications = Notification.objects.filter(
#         recipient=user,
#         is_read=False,
#         category__in=["saler_car_details", "inspection_assignment"]
#     ).order_by("-created_at")

#     serializer = NotificationSerializer(notifications, many=True)

#     return Response(serializer.data, status=status.HTTP_200_OK)



# Single notication read APi
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notification_as_read(request, notification_id):
    try:
        notification = Notification.objects.get(
            id=notification_id, recipient=request.user
        )
        notification.is_read = True
        notification.save()

        return Response(
            {"success": True, "message": "Notification marked as read"},
            status=status.HTTP_200_OK
        )
    except Notification.DoesNotExist:
        return Response(
            {"success": False, "message": "Notification not found"},
            status=status.HTTP_404_NOT_FOUND
        )

# multiple notification read
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_multiple_notifications_as_read(request):
    notification_ids = request.data.get("notification_ids", [])
    updated = Notification.objects.filter(
        id__in=notification_ids, recipient=request.user
    ).update(is_read=True)

    return Response(
        {"success": True, "updated_count": updated},
        status=status.HTTP_200_OK
    )  



# fetch assign slots
# @api_view(["GET"])
# @permission_classes([IsAuthenticated])
# def get_assigned_slots(request):
#     user = request.user

#     if user.role == "inspector":
#         slots = SelectedSlot.objects.filter(inspector=user)
#     elif user.role == "saler":
#         slots = SelectedSlot.objects.filter(saler_car__user=user)
#     else:
#         return Response(
#             {"message": "Unauthorized role."}, status=status.HTTP_403_FORBIDDEN
#         )

#     # Serialize the slots
#     serializer = SelectedSlotSerializer(slots, many=True)
#     return Response(
#         {
#             "message": "Assigned slots fetched successfully.",
#             "slots": serializer.data,
#         },
#         status=status.HTTP_200_OK,
#     )


# saler_car_detail sets is_manual = True
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_is_manual(request, car_id):
    try:
        car = saler_car_details.objects.get(pk=car_id)
        car.is_manual = True
        car.save(update_fields=["is_manual"])
        return Response({"message": "updated"}, status=status.HTTP_201_CREATED)
    except saler_car_details.DoesNotExist:
        return Response({"message": "car not found"}, status=status.HTTP_404_NOT_FOUND)


# on selecting slot
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_is_booked(request, car_id):
    try:
        car = saler_car_details.objects.get(pk=car_id)
        car.is_booked = True
        car.save(update_fields=["is_booked"])
        return Response({"message": "updated"}, status=status.HTTP_201_CREATED)
    except saler_car_details.DoesNotExist:
        return Response({"message": "car not found"}, status=status.HTTP_404_NOT_FOUND)


# update the car status
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_status(request, car_id):
    try:
        car = saler_car_details.objects.get(saler_car_id=car_id)
        new_status = request.data.get("status")

        valid_status = dict(saler_car_details.STATUS_CHOICES).keys()
        if new_status not in valid_status:
            return Response(
                {"Error": "invalid Status"}, status=status.HTTP_400_BAD_REQUEST
            )
        car.status = new_status
        car.save()

        return Response(
            {"message": "Status updated successfully", "new status": car.status},
            status=status.HTTP_200_OK,
        )

    except saler_car_details.DoesNotExist:
        return Response({"Error": "Not Found"}, status=status.HTTP_404_NOT_FOUND)


# get seller manual entries
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def seller_manual_entries(request , inspector_id):
    try:
        inspector = User.objects.get(id=inspector_id)
    except User.DoesNotExist:
        return Response({"error": "Inspector not found"}, status=404)

    manual_cars = saler_car_details.objects.filter(inspector=inspector, is_manual=True)

    serializer = SalerCarDetailsSerializer(manual_cars, many=True)

    return Response(serializer.data)



# is_inspected true
@api_view(["POST"])
def mark_as_inspected(request, car_id):
    car = get_object_or_404(saler_car_details, saler_car_id=car_id)
    car.is_inspected = True
    car.save()
    return Response(
        {"message": "Car marked as inspected", "is_inspected": car.is_inspected}
    )

    # /////////////////////////////////////////////////////////////////////////////////////////////////


# for inspector whose date time selected
# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def inspector_web_appointments(request):
#     inspector = request.user

#     cars = saler_car_details.objects.filter(inspector=inspector)

#     serializer = SalerCarDetailsSerializer(cars , many=True)

#     return Response(serializer.data ,status=status.HTTP_200_OK)

# web seller posted add
# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def seller_posted_add(request):
#     user = request.user

#     cars = saler_car_details.objects.filter(user=user).order_by('created_at')

#     serializer = SalerCarDetailsSerializer(cars, many=True)

#     return Response(serializer.data, status=status.HTTP_200_OK)

# Get free and reserved slots for an inspector
# @api_view(["GET"])
# @permission_classes([AllowAny])
# def get_free_slots(request):
#     date = request.query_params.get("date", None)
#     inspector_id = request.query_params.get("inspector", None)

#     if not inspector_id:
#         return Response(
#             {"message": "Inspector ID is required."}, status=status.HTTP_400_BAD_REQUEST
#         )
#     if date:
#         try:
#             date_obj = datetime.strptime(date, "%Y-%m-%d").date()
#         except ValueError:
#             return Response(
#                 {"message": "Invalid date format. Use YYYY-MM-DD."},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )
#     else:
#         date_obj = None
#     availability_queryset = Availability.objects.filter(inspector_id=inspector_id)
#     if date_obj:
#         availability_queryset = availability_queryset.filter(date=date_obj)

#     if not availability_queryset.exists():
#         return Response(
#             {
#                 "message": "No availability records found for the given inspector and date."
#             },
#             status=status.HTTP_404_NOT_FOUND,
#         )

#     # Fetch reserved slots
#     reserved_slots_queryset = SelectedSlot.objects.filter(inspector_id=inspector_id)
#     if date_obj:
#         reserved_slots_queryset = reserved_slots_queryset.filter(date=date_obj)

#     unique_reserved_slots = {}

#     for slot in reserved_slots_queryset:
#         key = (slot.date, slot.inspector, str(slot.time_slot)[:5])  # Unique identifier

#         if key not in unique_reserved_slots:
#             unique_reserved_slots[key] = {
#                 "slot_id": slot.id,
#                 "date": slot.date.strftime("%Y-%m-%d"),
#                 "inspector": slot.inspector.username,
#                 "time_slot": str(slot.time_slot)[:5],
#             }

#     reserved_slots = list(unique_reserved_slots.values())
#     taken_slots = set(
#         slot.time_slot.strftime("%H:%M") for slot in reserved_slots_queryset
#     )

#     # Fetch free slots
#     free_slots = []
#     for availability in availability_queryset:
#         available_time_slots = availability.time_slots
#         available_free_slots = [
#             str(slot) for slot in available_time_slots if str(slot) not in taken_slots
#         ]

#         for slot in available_free_slots:
#             free_slots.append(
#                 {
#                     "availability_id": availability.id,
#                     "date": availability.date.strftime("%Y-%m-%d"),
#                     "inspector": availability.inspector.username,
#                     "time_slot": slot,  # Already stored as HH:MM
#                 }
#             )

#     return Response(
#         {
#             "message": "Fetched slots successfully",
#             "free_slots": free_slots,
#             "reserved_slots": reserved_slots,
#         },
#         status=status.HTTP_200_OK,
#     )


# @api_view(["POST"])
# @permission_classes([IsAuthenticated])
# def post_inspection_report(request):
#     user = request.user
#     if user.role != "inspector":
#         return Response(
#             {"message": "Only inspectors can submit"},
#             status=status.HTTP_400_BAD_REQUEST,
#         )

#     data = request.data
#     print("Inspection report:", data)

#     # Safely get saler_car from request
#     saler_car = data.get("saler_car")
#     if not saler_car:
#         return Response(
#             {"message": "Missing 'saler_car' in request."},
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     try:
#         # Try to get the car based on the saler_car ID
#         car = saler_car_details.objects.get(saler_car_id=saler_car)
#     except saler_car_details.DoesNotExist:
#         return Response({"message": "Car not found"}, status=status.HTTP_404_NOT_FOUND)

#     # Decode base64 car photos if any
#     car_photos = data.get("car_photos", [])
#     decoded_photos = []
#     for index, photo in enumerate(car_photos):
#         try:
#             format, imgstr = photo.split(";base64,")
#             ext = format.split("/")[-1]
#             decoded_photos.append(f"data:image/{ext};base64,{imgstr}")
#         except Exception as e:
#             return Response(
#                 {"message": f"Error processing image: {str(e)}"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#     # Inject decoded photos into request data
#     mutable_data = request.data.copy()
#     mutable_data["car_photos"] = decoded_photos

#     # Use serializer to create the report
#     serializer = InspectionReportSerializer(data=mutable_data)
#     if serializer.is_valid():
#         report = serializer.save(inspector=user, saler_car=car)

#         # Send notifications to car owner, dealers, and admins
#         try:
#             if car.user:
#                 Notification.objects.create(
#                     recipient=car.user,
#                     message=f"Your car '{car.car_name} ({car.model})' has been inspected by {user.username}.",
#                     category="Your_car_inspected",
#                     saler_car=car,
#                 )
#                 logger.info(f"Notification sent to car owner: {car.user.username}")

#             dealers = User.objects.filter(role="dealer")
#             logger.info(f"Found {dealers.count()} dealers.")
#             for dealer in dealers:
#                 Notification.objects.create(
#                     recipient=dealer,
#                     message=f"The car '{car.car_name} ({car.model})' has been inspected. Check the inspection report.",
#                     category="dealer_car_inspected",
#                     saler_car=car,
#                 )

#             admins = User.objects.filter(role="admin")
#             logger.info(f"Found {admins.count()} admins.")
#             for admin in admins:
#                 Notification.objects.create(
#                     recipient=admin,
#                     message=f"The car '{car.car_name} ({car.model})' has been inspected. The inspection report is available.",
#                     category="admin_car_inspected",
#                     saler_car=car,
#                 )

#             logger.info("All notifications created successfully.")
#         except Exception as e:
#             logger.error(f"Error while creating notifications: {str(e)}")

#         return Response(
#             {
#                 "message": "Inspection report submitted successfully",
#                 "report": InspectionReportSerializer(report).data,
#             },
#             status=status.HTTP_201_CREATED,
#         )
#     else:
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# SALER SEE ONLY ITS APPOINTMENT WITH INSPECTOR Time selected by selller
# @api_view(["GET"])
# @permission_classes([IsAuthenticated])
# def saler_appointmet(request):
#     user = request.user

#     if user.role != "saler":
#         return Response(
#             {"Message": "Only Saler can view their appointment"},
#             status=status.HTTP_403_FORBIDDEN,
#         )

#     # Fetch all appointments related to the seller
#     appointments = SelectedSlot.objects.filter(saler_car__user=user).select_related(
#         "saler_car", "inspector"
#     )

#     appointments_data = []

#     for appointment in appointments:
#         # Convert date & time to a timezone-aware datetime object
#         appointment_datetime = timezone.make_aware(
#             datetime.combine(appointment.date, appointment.time_slot)
#         )
#         remaining_seconds = (appointment_datetime - timezone.now()).total_seconds()
#         remaining_days = int(remaining_seconds // (24 * 3600))
#         remaining_hours = int(
#             (remaining_seconds % (24 * 3600)) // 3600
#         )
#         remaining_minutes = int(
#             (remaining_seconds % 3600) // 60
#         )
#         remaining_secs = int(remaining_seconds % 60)

#         # Append data to list
#         appointments_data.append(
#             {
#                 "appointment_id": appointment.id,
#                 "car_id":appointment.saler_car.saler_car_id,
#                 "car_name": appointment.saler_car.car_name,
#                 "company": appointment.saler_car.company,
#                 "car_year": appointment.saler_car.model,
#                 "is_inspected": appointment.saler_car.is_inspected,
#                 "appointment_date": appointment.date.strftime("%Y-%m-%d"),
#                 "car_photos": appointment.saler_car.photos,
#                 "appointment_time": appointment.time_slot.strftime("%H:%M"),
#                 "inspector_first_name": appointment.inspector.first_name,
#                 "inspector_last_name": appointment.inspector.last_name,
#                 "inspector_phone_number": appointment.inspector.phone_number,
#                 "inspector_adress": appointment.inspector.adress,
#                 "inspector_email": appointment.inspector.email,
#                 "remaining_days": remaining_days,
#                 "remaining_hours": remaining_hours,
#                 "remaining_minutes": remaining_minutes,
#                 "remaining_seconds": remaining_secs,
#             }
#         )


#     return Response({"appointments": appointments_data}, status=status.HTTP_200_OK)


# INSPECTOR CAN SEE ALL APPOINTMENTS
# @api_view(["GET"])
# @permission_classes([IsAuthenticated])
# def inspector_appointments(request):
#     """Fetch all appointments for an inspector where the seller is not null."""
#     user = request.user

#     if user.role != "inspector":
#         return Response(
#             {"message": "Only inspectors can view this data"},
#             status=status.HTTP_403_FORBIDDEN,
#         )
#     appointments = (
#         SelectedSlot.objects.filter(inspector=user)
#         .filter(
#             Q(saler_car__user__isnull=False)
#             & Q(saler_car__is_manual=False)
#         )
#         .order_by("date", "time_slot")
#     )
#     if not appointments.exists():
#         return Response(
#             {"message": "No valid appointments found for this inspector"},
#             status=status.HTTP_404_NOT_FOUND,
#         )

#     unique_appointments = {}
#     now = timezone.now()

#     for appointment in appointments:
#         car_id = appointment.saler_car.saler_car_id

#         if car_id not in unique_appointments:
#             appointment_datetime = datetime.combine(
#                 appointment.date, appointment.time_slot
#             )
#             if timezone.is_naive(appointment_datetime):
#                 appointment_datetime = timezone.make_aware(appointment_datetime)

#             remaining_seconds = max(
#                 0, int((appointment_datetime - now).total_seconds())
#             )
#             remaining_days = remaining_seconds // (24 * 3600)
#             remaining_hours = (remaining_seconds % (24 * 3600)) // 3600
#             remaining_minutes = (remaining_seconds % 3600) // 60
#             remaining_secs = remaining_seconds % 60

#             unique_appointments[car_id] = {
#                 "appointment_id": appointment.id,
#                 "car_id": car_id,
#                 "seller_first_name": (
#                     appointment.saler_car.user.first_name
#                     if appointment.saler_car.user
#                     else "N/A"
#                 ),
#                 "seller_last_name": (
#                     appointment.saler_car.user.last_name
#                     if appointment.saler_car.user
#                     else "N/A"
#                 ),
#                 "seller_phone_number": (
#                     appointment.saler_car.user.phone_number
#                     if appointment.saler_car.user
#                     else "N/A"
#                 ),
#                 "seller_email": (
#                     appointment.saler_car.user.email
#                     if appointment.saler_car.user
#                     else "N/A"
#                 ),
#                 "car_name": appointment.saler_car.car_name,
#                 "car_company": appointment.saler_car.company,
#                 "car_model": appointment.saler_car.model,
#                 "car_color": appointment.saler_car.color,
#                 "car_condition": appointment.saler_car.condition,
#                 "car_demand": appointment.saler_car.demand,
#                 "car_city": appointment.saler_car.city,
#                 "is_sold": appointment.saler_car.is_sold,
#                 "mileage": appointment.saler_car.milage,
#                 "description": appointment.saler_car.description,
#                 "type": appointment.saler_car.type,
#                 "fuel_type": appointment.saler_car.fuel_type,
#                 "registered_in": appointment.saler_car.registered_in,
#                 "assembly": appointment.saler_car.assembly,
#                 "engine_capacity": appointment.saler_car.engine_capacity,
#                 "photos": [
#                     (
#                         f"data:image/jpeg;base64,{photo}"
#                         if not photo.startswith("data:image")
#                         else photo
#                     )
#                     for photo in appointment.saler_car.photos
#                 ],
#                 "status": appointment.saler_car.status,
#                 "created_at": appointment.saler_car.created_at.strftime(
#                     "%Y-%m-%d %H:%M:%S"
#                 ),
#                 "updated_at": appointment.saler_car.updated_at.strftime(
#                     "%Y-%m-%d %H:%M:%S"
#                 ),
#                 "is_inspected": appointment.saler_car.is_inspected,
#                 "added_by": (
#                     appointment.saler_car.added_by
#                     if hasattr(appointment.saler_car, "added_by")
#                     else None
#                 ),
#                 "inspector": (
#                     appointment.inspector.id if appointment.inspector else None
#                 ),
#                 "date": appointment.date.strftime("%Y-%m-%d"),
#                 "time_slot": appointment.time_slot.strftime("%H:%M:%S"),
#                 "remaining_days": remaining_days,
#                 "remaining_hours": remaining_hours,
#                 "remaining_minutes": remaining_minutes,
#                 "remaining_seconds": remaining_secs,
#                 "selected_by": appointment.booked_by,
#             }

#     return Response(
#         {
#             "message": "Inspector appointments retrieved successfully",
#             "appointments": list(unique_appointments.values()),
#         },
#         status=status.HTTP_200_OK,
#     )


# cloudinary views


@csrf_exempt
def delete_images(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            public_ids = data.get("public_ids")

            if not public_ids or not isinstance(public_ids, list):
                return JsonResponse(
                    {"error": "public_ids (list) is required"}, status=400
                )

            # Delete images from Cloudinary
            result = cloudinary.api.delete_resources(public_ids)

            return JsonResponse(
                {"message": "Images deleted from Cloudinary", "result": result}
            )

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "POST method required"}, status=400)
