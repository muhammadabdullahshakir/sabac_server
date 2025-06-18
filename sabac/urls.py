from django.urls import path
from .views import (
    register,
    get_free_slots,
    is_authentecated,
    add_availability,
    select_slot, #not used now
    get_selected_slots,
    post_inspection_report,
    get_inspection_report,
    saler_register,
    add_car_details,
    get_car_details,
    # get_notifications, not used
    # get_inspection_notifications,
    get_notifications,
    get_cars_list,
    get_seller_appointment_notification,
    assign_slot,
    get_assigned_slots,
    get_appointment_notification,
    place_bid,
    view_car_bids,
    accept_bid,
    view_dealer_bids,
    update_car_details,
    saler_update,
    delete_saler,
    delete_user,
    edit_user,
    get_last_car_details,
    assign_inspector_to_car,
    delete_ad,
    update_ad,
    post_inspection_report_mob
)
from .views import (
    get_list_of_car_for_inspection,
    get_inspectors,
    saler_appointmet,
    inspector_appointments,
    update_status,
    get_bidding_cars,
    get_upcoming_cars,
    approve_inspection,
    get_cars_for_approval,
    mark_bid_notifications_as_read,
    # post_guest_details,
    get_cars_count,
    update_is_manual,
    update_is_booked,
    update_inspection_report,
    get_reviewd_inspection,
)
from .views import (
    # get_assigned_slots,
    mark_notifications_as_read,
    post_additional_details,
    get_user_cars,
    reject_inspection,
    bid_notification,
    reject_bid,
    guest_add_car_details,
    get_guest_car_details,
    seller_manual_entries,
    get_highest_bid,
    logout,
    mark_as_inspected,
    saler_manual_entry,
    usersList,
    get_user_count,
    get_cars_count,
    carsStats,
    dealer_inventory,
    dealer_register,
    inspector_register,
    dealer_update,
    inspector_update,
    admin_register,
    admin_update,
    dealersList,
    inspectorsList,
    adminList,
    get_all_bidding,
    get_all_sold_cars,
    bid_notification_for_seller,
    assign_inspector_to_guest_car,
    get_inspector_appointmnet_by_guest,
    get_manual_guest_cars_for_inspector,
    mark_guest_car_as_inspected,
    # post_guest_inspection_report,
    delete_images,
    guest_inspection_report_post,
    post_guest_inspection_report_mob,
    update_car_status,
    get_inspection_report_guest,
    get_upcoming_cars_by_guest,
    get_bidding_cars_by_guest,
    approve_guest_inspection,
    reject_guest_inspection,
    # get_assigned_slots,
    get_manual_entries_for_inspector,
    get_manual_saler_assigned_slots,
    mark_multiple_notifications_as_read,
    mark_notification_as_read,
    get_cars_data


)

urlpatterns = [

    path("authentecation/", is_authentecated),  # check authentecation
    path("logout/", logout, name="logout"),
    path("get_cars_data/",get_cars_data,name="get_cars_data"), #json of all cars

    path(
        "add_availability/", add_availability, name="add_availability"
    ),  # add availability url
    path("select_slot/", select_slot, name="select_slot"),
    path(
        "get_selected_slots/", get_selected_slots, name="get_selected_slots"
    ),  # get selected slots
    path(
        "get_free_slots/", get_free_slots, name="get_free_slots"
    ),  # get available slots
    path(
        "post_inspection_report/", post_inspection_report, name="post_inspection_report"
    ),  # post inspection report
    path(
        "post_inspection_report_mob/", post_inspection_report_mob, name="post_inspection_report_mob"
    ),  # post inspection report
    path(
        "get_inspection_report/", get_inspection_report, name="get_inspection_report"
    ),  # get inspection report of specefic car
    path(
        "saler_register/", saler_register, name="saler_register"
    ),  # url only saler can register by this
    path(
        "add_car_details/", add_car_details, name="add_car_details"
    ),  # saler post saler car details
    # seller update its car detail
    path("update_ad/<int:car_id>", update_ad, name="update_ad"),
    # seller selete its posted car
    path("delete_ad/<int:car_id>", delete_ad, name="ad delete"),

    path(
        "get_car_details/", get_car_details, name="get_car_details"
    ),  # get saler car details
    # path(
    #     "notifications/", get_notifications, name="get_notifications"
    # ),  # get notification for inspector when seller or guest ad post
    path(
        "get_notifications/",
        get_notifications,
        name="get_notifications",
    ),  # saler gets inspection notification

    path(
        "get_seller_appointment_notification/",
        get_seller_appointment_notification,
        name="get_seller_appointment_notification",
    ),  # seler select slot send notification to inspector
    # path('assign_slot/',assign_slot,name='assign_slot'), #inspector sets appointment
    # path('get_assigned_slots/',get_assigned_slots,name='get_assigned_slots'), #get assign slots
    path(
        "get_appointment_notification/",
        get_appointment_notification,
        name="get_appointment_notification",
    ),  # when inspecor gives time to saler
    path("place_bid/", place_bid, name="place_bid"),  # dealer posted bids



    path(
        "view_dealer_bids/", view_dealer_bids, name="view_dealer_bids"
    ),  # dealer view own bids
    path(
        "update_car_details/<int:car_id>/",
        update_car_details,
        name="update_car_details",
    ),  # slaer update its car details
    path(
        "saler_update/", saler_update, name="saler_update"
    ),  # saler update own details
    path("delete_saler/", delete_saler,
         name="delete_saler"),  # saler delete itself

    path(
        "get_last_car_details/", get_last_car_details, name="get_last_car_details"
    ),  # for seller show its last car posted
    path(
        "get_list_of_car_for_inspection/",
        get_list_of_car_for_inspection,
        name="get_list_of_car_for_inspection",
    ),  # list of all sellers cars for inspection
    path(
        "get_inspectors/", get_inspectors, name="get_inspectors"
    ),  # list of inspectors
    path(
        "saler_appointmet/", saler_appointmet, name="saler_appointmet"
    ),  # seller view own appointment
    path(
        "inspector_appointments/", inspector_appointments, name="inspector_appointments"
    ),  # inspector view appointments with sellers
    path(
        "assign_slot/", assign_slot, name="assign-slot"
    ),  # inspector assign slot to seller
    path("get_assigned_slots/", get_assigned_slots, name="get_assign_slots"),
    path(
        "mark_notifications_as_read/",
        mark_notifications_as_read,
        name="mark_notifications_as_read",
    ),
    path(
        "post_additional_details/",
        post_additional_details,
        name="post_additional_details",
    ),  # saler name and number for inspection
    path(
        "get_user_cars/", get_user_cars, name="get_user_cars"
    ),  # list of saler cars on saler view
    path(
        "update_status/<int:car_id>/", update_status, name="update_status"
    ),  # updated the status of car like pending ,bidding
    path(
        "get_bidding_cars/", get_bidding_cars, name="get_bidding_cars"
    ),  # cars list with status bidding
    path(
        "get_upcoming_cars/", get_upcoming_cars, name="get_upcoming_cars"
    ),  # upcoming cars status in_inspection for dealer
    # fetch bid notification for seller
    path(
        "mark_bid_notifications_as_read/",
        mark_bid_notifications_as_read,
        name="mark_bid_notifications_as_read",
    ),
    # path(
    #     "post_guest_details/", post_guest_details, name="post_guest_details"
    # ),  # guest add basic detail
  # list of cars of guests
    path(
        "assign_inspector_to_car/",
        assign_inspector_to_car,
        name="assign_inspector_to_car",
    ),  # link car to specefic inspector for manual entry
    path(
        "seller_manual_entries/<int:inspector_id>/", seller_manual_entries, name="seller_manual_entries"
    ),  # seller carss list manual entries for inspector///////////////////////////////////
    path("mark-inspected/<int:car_id>/",
         mark_as_inspected, name="mark_as_inspected"),
    # path('assign-inspector-to-seller-car/', assign_inspector_to_seller_car, name='assign_inspector_to_seller_car'),
    path(
        "get_cars_count/", get_cars_count, name="get_cars_count"
    ),  # cars with status bidding count
    path(
        "get_highest_bid/", get_highest_bid, name="get_highest_bid"
    ),  # highest bid of all
    path(
        "update_is_manual/<int:car_id>/", update_is_manual, name="update_is_manual"
    ),  # update the car is_manual
    path(
        "update_is_booked/<int:car_id>/", update_is_booked, name="update_is_booked"
    ),  # update the car is_booked
    path("saler_manual_entry/", saler_manual_entry,
         name="saler_manual_entry"),  # seller manual entries
    path('update_inspection_report/<int:report_id>/',
         update_inspection_report, name='update_inspection_report'),
    path('get_reviewd_inspection/', get_reviewd_inspection,
         name="get_reviewd_inspection"),
    path("dealer_inventory/", dealer_inventory,
         name="dealer_inventory"),  # dealer invenntory


    # admin
    path('users/', usersList, name="users-list"),
    path("register/", register, name="register"),
    path("get_cars_list/", get_cars_list,
         name="get_cars_list"),  # list of all cars
    path("view_car_bids/<int:car_id>/", view_car_bids,
         name="view_car_bids"),  # bids on car
    path("accept_bid/<int:bid_id>/", accept_bid,
         name="accept_bid"),  # saler accept bid
    path("reject_bid/<int:bid_id>/", reject_bid,
         name="reject_bid"),  # saler reject bid
    # admin delete other user
    path("delete_user/", delete_user, name="delete_user"),
    path("edit_user/", edit_user, name="edit_user"),  # admin edit user
    path("approve_inspection/<int:report_id>", approve_inspection,
         name="approve_inspection"),  # admin inspection approving url
    path("reject_inspection/<int:report_id>", reject_inspection,
         name="reject_inspection"),  # admin reject inspection
    path("get_cars_for_approval/", get_cars_for_approval,
         name="get_cars_for_approval"),  # get cars for admin with await_approval
    path("Bid_notification/", bid_notification,
         name="bid_notification"),
    path("user-count/", get_user_count, name="user-count"),
    path("cars-count/", get_cars_count, name="cars-count"),
    path("car-posting-stats/", carsStats, name="car-stats"),
    path("dealer_register/", dealer_register, name="dealer_register"),
    path("inspector_register/", inspector_register, name="inspector_register"),
    path("dealer-update/<int:dealer_id>/", dealer_update, name="dealer_update"),
    path("inspector_update/<int:inspector_id>/",
         inspector_update, name="inspector_update"),
    path("admin_register/", admin_register, name="admin_register"),
    path("admin_update/<int:admin_id>/", admin_update, name="admin_update"),
    path("dealers/", dealersList, name="dealers"),
    path("inspectors/", inspectorsList, name="inspectors"),
    path("adminList/", adminList, name="adminList"),
    path("get_all_bidding/", get_all_bidding, name="get_all_bidding"),
    path("live-cars/", get_all_sold_cars, name="get_all_sold_cars"),
    path("bid_notification_for_seller/",bid_notification_for_seller,name="bid_notification_for_seller"),
    
    
    
    path(
        "guest_add_car_details/", guest_add_car_details, name="guest_add_car_details"
    ),  # guest post car for sale
    path(
        "get_guest_car_details/", get_guest_car_details, name="get_guest_car_details"
    ),
    path("assign_inspector_to_guest_car/",assign_inspector_to_guest_car,name="assign_inspector_to_guest_car"),
    path("get_inspector_appointmnet_by_guest/",get_inspector_appointmnet_by_guest,name="get_inspector_appointmnet_by_guest"),
    path("get_manual_guest_cars_for_inspector/",get_manual_guest_cars_for_inspector,name="get_manual_guest_cars_for_inspector"), #not used
    path("mark_guest_car_as_inspected/<int:id>/",mark_guest_car_as_inspected,name="mark_guest_car_as_inspected"),
    # path("post_guest_inspection_report/",post_guest_inspection_report,name="post_guest_inspection_report"),
    path("delete/",delete_images,name="delete_images"), #cloudinary delete view
    path("guest_inspection_report_post/",guest_inspection_report_post,name="guest_inspection_report_post"),
    path("post_guest_inspection_report_mob/",post_guest_inspection_report_mob,name="post_guest_inspection_report_mob"),
    path("update_car_status/<int:guest_car_id>/",update_car_status,name="update_car_status"),
    path("get_inspection_report_guest/",get_inspection_report_guest,name="get_inspection_report_guest"),
    path("get_upcoming_cars_by_guest/",get_upcoming_cars_by_guest,name="get_upcoming_cars_by_guest"),
    path("get_bidding_cars_by_guest/",get_bidding_cars_by_guest,name="get_bidding_cars_by_guest"),
    path("approve_guest_inspection/<int:report_id>/",approve_guest_inspection,name="approve_guest_inspection"),
    path("reject_guest_inspection/<int:report_id>/",reject_guest_inspection,name="reject_guest_inspection"),
    # path("get_assigned_slots/",get_assigned_slots,name="get_assigned_slots"),
    path("get_manual_entries_for_inspector/",get_manual_entries_for_inspector,name="get_manual_entries_for_inspector"),
    path("get_manual_saler_assigned_slots/",get_manual_saler_assigned_slots,name="get_manual_saler_assigned_slots"),
    path("mark_multiple_notifications_as_read/",mark_multiple_notifications_as_read,name="mark_multiple_notifications_as_read"),
    path("mark_notification_as_read/<int:notification_id>/",mark_notification_as_read,name="mark_notification_as_read")
    
    








    # web apis
    # path("add_car_details_web/",add_car_details_web, name="add_car_details_web"), #from web car detaail add
    # path("inspector_web_appointments/",inspector_web_appointments, name="inspector_web_appointments"),


]
