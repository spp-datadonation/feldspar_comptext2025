from port.api.assets import *
from port.api.props import Translatable
import pandas as pd
from datetime import datetime, timezone, timedelta
import re

############################
# Helper functions for extraction
############################


# convert timespamp
def epoch_to_date(epoch_timestamp: str | int) -> str:
    """
    Convert epoch timestamp to an ISO 8601 string. Assumes UTC +1

    If timestamp cannot be converted raise CannotConvertEpochTimestamp
    """

    try:
        epoch_timestamp = int(epoch_timestamp)
        out = datetime.fromtimestamp(
            epoch_timestamp, tz=timezone(timedelta(hours=1))
        ).isoformat()  # timezone = utc + 1

    except:
        # fake date if unable to convert
        out = "01-01-1999"

    out = pd.to_datetime(out)
    return out.date().strftime(
        "%d-%m-%Y"
    )  # convertion to string for display in browser


# translate outputs
def translate(value, locale, dummy_decider=None):
    if value == "date":
        translatedMessage = Translatable(
            {
                "en": "Date",
                "de": "Datum",
                "nl": "Datum",
            }
        )
        return translatedMessage.translations[locale]

    if value == "dummy":
        if dummy_decider in [True, "True"]:
            translatedMessage = Translatable(
                {
                    "en": "Yes",
                    "de": "Ja",
                    "nl": "Ja",
                }
            )
        elif dummy_decider in [False, "False"]:
            translatedMessage = Translatable(
                {
                    "en": "No",
                    "de": "Nein",
                    "nl": "Nee",
                }
            )
        else:
            translatedMessage = Translatable(
                {
                    "en": str(dummy_decider),
                    "de": str(dummy_decider),
                    "nl": str(dummy_decider),
                }
            )
        return translatedMessage.translations[locale]

    else:
        translatedMessage = Translatable(value)
        return translatedMessage.translations[locale]


############################
# Extraction functions
############################


def extract_time_spent(combined_data, locale):
    """
    Calculate the total time spent on Instagram per day.
    A session continues if the time between views is less than 60 seconds.
    Sessions reset at midnight.

    Works with either posts_viewed, videos_watched, or both.
    """

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Time spent (seconds)",
            "de": "Verbrachte Zeit (Sekunden)",
            "nl": "Bestede tijd (seconden)",
        },
        locale,
    )

    # Constants
    SESSION_BREAK_THRESHOLD = 60  # seconds
    DEFAULT_ACTIVITY_TIME = 30  # seconds for the last activity in a session

    # Extract data from the combined format
    posts_viewed_json = combined_data.get("posts_viewed", {})
    videos_watched_json = combined_data.get("videos_watched", {})

    # Get timestamps from post views (if available)
    post_timestamps = []
    if posts_viewed_json:
        post_timestamps = [
            entry["string_map_data"]["Time"]["timestamp"]
            for entry in posts_viewed_json.get("impressions_history_posts_seen", [])
            if "Time" in entry["string_map_data"]
        ]

    # Get timestamps from video views (if available)
    video_timestamps = []
    if videos_watched_json:
        video_timestamps = [
            entry["string_map_data"]["Time"]["timestamp"]
            for entry in videos_watched_json.get(
                "impressions_history_videos_watched", []
            )
            if "Time" in entry["string_map_data"]
        ]

    # Combine and sort all timestamps
    all_timestamps = sorted(post_timestamps + video_timestamps)

    if not all_timestamps:
        return pd.DataFrame(columns=[tl_date, tl_value])

    # Calculate time spent per day
    from datetime import datetime

    daily_time_spent = {}
    session_start_time = None
    last_time = None
    current_day = None

    for ts in all_timestamps:
        current_time = datetime.fromtimestamp(ts)
        new_day = current_time.date()

        # Initialize the day in our dictionary if needed
        if new_day not in daily_time_spent:
            daily_time_spent[new_day] = 0

        # Check if we're starting a new session
        start_new_session = False

        if last_time is None:
            # First activity
            start_new_session = True
        elif new_day != current_day:
            # Day changed, end previous session and start new one
            if session_start_time:
                session_time = (
                    last_time - session_start_time
                ).total_seconds() + DEFAULT_ACTIVITY_TIME
                daily_time_spent[current_day] += session_time
            start_new_session = True
        elif (current_time - last_time).total_seconds() > SESSION_BREAK_THRESHOLD:
            # More than threshold time since last activity, end session and start new
            if session_start_time:
                session_time = (
                    last_time - session_start_time
                ).total_seconds() + DEFAULT_ACTIVITY_TIME
                daily_time_spent[current_day] += session_time
            start_new_session = True

        if start_new_session:
            session_start_time = current_time

        # Update for the next iteration
        last_time = current_time
        current_day = new_day

    # Handle the last session
    if session_start_time and last_time:
        session_time = (
            last_time - session_start_time
        ).total_seconds() + DEFAULT_ACTIVITY_TIME
        daily_time_spent[current_day] += session_time

    # Convert to DataFrame
    dates = [
        epoch_to_date(int(datetime(d.year, d.month, d.day).timestamp()))
        for d in daily_time_spent.keys()
    ]
    times = [round(t) for t in daily_time_spent.values()]  # Round to whole seconds

    result_df = pd.DataFrame({tl_date: dates, tl_value: times})
    result_df = result_df.sort_values(by=tl_date).reset_index(drop=True)

    return result_df


def extract_session_frequency(combined_data, locale):
    """
    Calculate how many Instagram sessions a user had per day.
    A session is defined as a sequence of activities with less than 60 seconds between them.
    Sessions reset at midnight.

    Works with either posts_viewed, videos_watched, or both.
    """

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Number of sessions",
            "de": "Anzahl der Sitzungen",
            "nl": "Aantal sessies",
        },
        locale,
    )

    # Constants
    SESSION_BREAK_THRESHOLD = 60  # seconds

    # Extract data from the combined format
    posts_viewed_json = combined_data.get("posts_viewed", {})
    videos_watched_json = combined_data.get("videos_watched", {})

    # Get timestamps from post views (if available)
    post_timestamps = []
    if posts_viewed_json:
        post_timestamps = [
            entry["string_map_data"]["Time"]["timestamp"]
            for entry in posts_viewed_json.get("impressions_history_posts_seen", [])
            if "Time" in entry["string_map_data"]
        ]

    # Get timestamps from video views (if available)
    video_timestamps = []
    if videos_watched_json:
        video_timestamps = [
            entry["string_map_data"]["Time"]["timestamp"]
            for entry in videos_watched_json.get(
                "impressions_history_videos_watched", []
            )
            if "Time" in entry["string_map_data"]
        ]

    # Combine and sort all timestamps
    all_timestamps = sorted(post_timestamps + video_timestamps)

    if not all_timestamps:
        return pd.DataFrame(columns=[tl_date, tl_value])

    # Count sessions per day
    from datetime import datetime

    daily_sessions = {}
    last_time = None
    current_day = None

    for ts in all_timestamps:
        current_time = datetime.fromtimestamp(ts)
        new_day = current_time.date()

        # Initialize the day in our dictionary if needed
        if new_day not in daily_sessions:
            daily_sessions[new_day] = 0

        # Check if we're starting a new session
        start_new_session = False

        if last_time is None:
            # First activity
            start_new_session = True
        elif new_day != current_day:
            # Day changed, start new session
            start_new_session = True
        elif (current_time - last_time).total_seconds() > SESSION_BREAK_THRESHOLD:
            # More than threshold time since last activity
            start_new_session = True

        if start_new_session:
            daily_sessions[new_day] += 1

        # Update for the next iteration
        last_time = current_time
        current_day = new_day

    # Convert to DataFrame
    dates = [
        epoch_to_date(int(datetime(d.year, d.month, d.day).timestamp()))
        for d in daily_sessions.keys()
    ]
    sessions = list(daily_sessions.values())

    result_df = pd.DataFrame({tl_date: dates, tl_value: sessions})
    result_df = result_df.sort_values(by=tl_date).reset_index(drop=True)

    return result_df


def extract_ads_seen(ads_seen_json, locale):
    """extract ads_information/ads_and_topics/ads_viewed -> list of authors per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {"en": "Seen accounts", "de": "Gesehene Konten", "nl": "Geziene accounts"},
        locale,
    )

    timestamps = [
        t["string_map_data"]["Time"]["timestamp"]
        for t in ads_seen_json["impressions_history_ads_seen"]
    ]  # get list with timestamps in epoch format (if author exists)
    dates = [epoch_to_date(t) for t in timestamps]  # convert epochs to dates
    authors = [
        i["string_map_data"]["Author"]["value"]
        if "Author" in i["string_map_data"]
        else translate(
            {
                "en": "Unknown account",
                "de": "Unbekanntes Konto",
                "nl": "Onbekend account",
            },
            locale,
        )
        for i in ads_seen_json["impressions_history_ads_seen"]
    ]  # not for all viewed ads there is an author!

    adds_viewed_df = pd.DataFrame({tl_date: dates, tl_value: authors})

    aggregated_df = adds_viewed_df.groupby(tl_date)[tl_value].agg(list).reset_index()

    return aggregated_df


def extract_ads_clicked(ads_clicked_json, locale):
    """extract ads_information/ads_and_topics/ads_clicked -> list of product names per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {"en": "Clicked ad", "de": "Angeklickte Werbung", "nl": "Geklikte advertentie"},
        locale,
    )

    timestamps = [
        t["string_list_data"][0]["timestamp"]
        for t in ads_clicked_json["impressions_history_ads_clicked"]
    ]  # get list with timestamps in epoch format
    dates = [epoch_to_date(t) for t in timestamps]  # convert epochs to dates
    products = [i["title"] for i in ads_clicked_json["impressions_history_ads_clicked"]]

    adds_clicked_df = pd.DataFrame({tl_date: dates, tl_value: products})

    aggregated_df = adds_clicked_df.groupby(tl_date)[tl_value].agg(list).reset_index()

    return aggregated_df


def extract_recently_viewed_items(recently_viewed_items_json, locale):
    """extract your_instagram_activity/shopping/recently_viewed_items -> list of items"""

    tl_value = translate(
        {
            "en": "Recently viewed items",
            "de": "Kürzlich gesehene Einkaufsartikel",
            "nl": "Recent bekeken items",
        },
        locale,
    )

    items = recently_viewed_items_json["checkout_saved_recently_viewed_products"]
    products = [p["string_map_data"]["Product Name"]["value"] for p in items]

    products_df = pd.DataFrame(products, columns=[tl_value])

    return products_df


def extract_posts_seen(posts_seen_json, locale):
    """extract ads_information/ads_and_topics/posts_viewed -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of viewed posts",
            "de": "Anzahl der gesehenen Posts",
            "nl": "Aantal bekeken berichten",
        },
        locale,
    )

    timestamps = [
        t["string_map_data"]["Time"]["timestamp"]
        for t in posts_seen_json["impressions_history_posts_seen"]
    ]  # get list with timestamps in epoch format
    dates = [epoch_to_date(t) for t in timestamps]  # convert epochs to dates
    postViewedDates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = postViewedDates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_videos_seen(videos_seen_json, locale):
    """extract ads_information/ads_and_topics/videos_watched -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of viewed videos",
            "de": "Anzahl der gesehenen Videos",
            "nl": "Aantal bekeken video's",
        },
        locale,
    )

    timestamps = [
        t["string_map_data"]["Time"]["timestamp"]
        for t in videos_seen_json["impressions_history_videos_watched"]
    ]  # get list with timestamps in epoch format
    dates = [epoch_to_date(t) for t in timestamps]  # convert epochs to dates
    videosViewedDates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = videosViewedDates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_paid_subscription(paid_subscription_json, locale):
    """extract ads_information/instagram_ads_and_businesses/subscription_for_no_ads -> dummy whether user has such a subscription"""

    tl_value = translate(
        {
            "en": "Subscription for no ads",
            "de": "Abo-Option für Werbefreiheit",
            "nl": "Abonnement zonder advertenties",
        },
        locale,
    )

    value = None

    if paid_subscription_json["label_values"][0]["value"] == "Inaktiv":
        value = translate("dummy", locale, False)
    else:
        value = translate("dummy", locale, True)

    return pd.DataFrame([value], columns=[tl_value])


def extract_blocked_profiles(blocked_profiles_json, locale):
    """extract connections/followers_and_following/blocked_accounts -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of blocked account",
            "de": "Anzahl blockierter Konten",
            "nl": "Aantal geblokkeerde accounts",
        },
        locale,
    )

    dates = [
        epoch_to_date(t["string_list_data"][0]["timestamp"])
        for t in blocked_profiles_json["relationships_blocked_users"]
    ]  # get list with timestamps in epoch format
    dates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = dates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_restricted_profiles(restricted_profiles_json, locale):
    """extract connections/followers_and_following/restricted_accounts -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of restricted accounts",
            "de": "Anzahl der eingeschränkten Konten",
            "nl": "Aantal beperkte accounts",
        },
        locale,
    )

    dates = [
        epoch_to_date(t["string_list_data"][0]["timestamp"])
        for t in restricted_profiles_json["relationships_restricted_users"]
    ]  # get list with timestamps in epoch format
    dates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = dates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_post_comments(post_comments_json, locale):
    """extract your_instagram_activity/comments/post_comments_1 -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of post comments",
            "de": "Anzahl der Post-Kommentare",
            "nl": "Aantal reacties op berichten",
        },
        locale,
    )

    # file can just be dict and not list if only one posted comment
    if isinstance(post_comments_json, dict):
        dates = [
            epoch_to_date(post_comments_json["string_map_data"]["Time"]["timestamp"])
        ]
    else:
        dates = [
            epoch_to_date(t["string_map_data"]["Time"]["timestamp"])
            for t in post_comments_json
        ]  # get list with timestamps in epoch format

    dates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = dates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_reel_comments(reel_comments_json, locale):
    """extract your_instagram_activity/comments/reels_comments -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of reel comments",
            "de": "Anzahl der Reel-Kommentare",
            "nl": "Aantal reacties op reels",
        },
        locale,
    )

    dates = [
        epoch_to_date(t["string_map_data"]["Time"]["timestamp"])
        for t in reel_comments_json["comments_reels_comments"]
    ]  # get list with timestamps in epoch format
    dates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = dates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_posts_liked(posts_liked_json, locale):
    """extract your_instagram_activity/likes/liked_posts -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of liked posts",
            "de": 'Anzahl "geliker" Posts',
            "nl": "Aantal gelikete berichten",
        },
        locale,
    )

    dates = [
        epoch_to_date(t["string_list_data"][0]["timestamp"])
        for t in posts_liked_json["likes_media_likes"]
    ]
    dates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = dates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_stories_liked(stories_liked_json, locale):
    """extract your_instagram_activity/story_sticker_interactions/story_likes -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of liked stories",
            "de": 'Anzahl "gelikter" Stories',
            "nl": "Aantal gelikete stories ",
        },
        locale,
    )

    dates = [
        epoch_to_date(t["string_list_data"][0]["timestamp"])
        for t in stories_liked_json["story_activities_story_likes"]
    ]  # get list with timestamps in epoch format
    dates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = dates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_comments_liked(comments_liked_json, locale):
    """extract your_instagram_activity/likes/liked_comments -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of liked comments",
            "de": 'Anzahl "geliker" Kommentare',
            "nl": "Aantal gelikete reacties",
        },
        locale,
    )

    dates = [
        epoch_to_date(t["string_list_data"][0]["timestamp"])
        for t in comments_liked_json["likes_comment_likes"]
    ]
    dates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = dates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_story_interaction_countdowns(story_interaction_countdowns_json, locale):
    """extract your_instagram_activity/story_sticker_interactions/countdowns -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of reactions",
            "de": "Anzahl der Reaktionen",
            "nl": "Aantal reacties",
        },
        locale,
    )

    dates = [
        epoch_to_date(t["string_list_data"][0]["timestamp"])
        for t in story_interaction_countdowns_json["story_activities_countdowns"]
    ]  # get list with timestamps in epoch format
    dates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = dates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_story_interaction_emoji_sliders(
    story_interaction_emoji_sliders_json, locale
):
    """extract your_instagram_activity/story_sticker_interactions/emoji_sliders -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of reactions",
            "de": "Anzahl der Reaktionen",
            "nl": "Aantal reacties",
        },
        locale,
    )

    dates = [
        epoch_to_date(t["string_list_data"][0]["timestamp"])
        for t in story_interaction_emoji_sliders_json["story_activities_emoji_sliders"]
    ]  # get list with timestamps in epoch format
    dates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = dates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_story_interaction_polls(story_interaction_polls_json, locale):
    """extract your_instagram_activity/story_sticker_interactions/polls -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of reactions",
            "de": "Anzahl der Reaktionen",
            "nl": "Aantal reacties",
        },
        locale,
    )

    dates = [
        epoch_to_date(t["string_list_data"][0]["timestamp"])
        for t in story_interaction_polls_json["story_activities_polls"]
    ]  # get list with timestamps in epoch format
    dates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = dates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_story_interaction_questions(story_interaction_questions_json, locale):
    """extract your_instagram_activity/story_sticker_interactions/questions -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of reactions",
            "de": "Anzahl der Reaktionen",
            "nl": "Aantal reacties",
        },
        locale,
    )

    dates = [
        epoch_to_date(t["string_list_data"][0]["timestamp"])
        for t in story_interaction_questions_json["story_activities_questions"]
    ]  # get list with timestamps in epoch format
    dates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = dates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_story_interaction_quizzes(story_interaction_quizzes_json, locale):
    """extract your_instagram_activity/story_sticker_interactions/quizzes -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of reactions",
            "de": "Anzahl der Reaktionen",
            "nl": "Aantal reacties",
        },
        locale,
    )

    dates = [
        epoch_to_date(t["string_list_data"][0]["timestamp"])
        for t in story_interaction_quizzes_json["story_activities_quizzes"]
    ]  # get list with timestamps in epoch format
    dates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = dates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_posts_created(posts_created_json, locale):
    """extract your_instagram_activity/content/posts_1 -> count per day + info about location"""

    tl_value = translate(
        {
            "en": ["Date", "Linked location"],
            "de": ["Datum", "Verlikter Standort"],
            "nl": ["Datum", "Locatie leuk gevonden"],
        },
        locale,
    )

    results = []

    # file can just be dict and not list if only one post
    if isinstance(posts_created_json, dict):
        for media in posts_created_json.get("media", []):
            date = epoch_to_date(media.get("creation_timestamp", ""))
            has_latitude_data = any(
                "latitude" in exif_data
                for exif_data in media.get("media_metadata", {})
                .get("photo_metadata", {})
                .get("exif_data", [])
            )

            results.append(
                {
                    tl_value[0]: date,
                    tl_value[1]: translate("dummy", locale, has_latitude_data),
                }
            )

    else:
        for post in posts_created_json:
            for media in post.get("media", []):
                date = epoch_to_date(media.get("creation_timestamp", ""))
                has_latitude_data = any(
                    "latitude" in exif_data
                    for exif_data in media.get("media_metadata", {})
                    .get("photo_metadata", {})
                    .get("exif_data", [])
                )

                results.append(
                    {
                        tl_value[0]: date,
                        tl_value[1]: translate("dummy", locale, has_latitude_data),
                    }
                )

    posts_df = pd.DataFrame(results)

    return posts_df


def extract_stories_created(stories_created_json, locale):
    """extract your_instagram_activity/content/stories -> count per day + info about location"""

    tl_value = translate(
        {
            "en": ["Date", "Linked location"],
            "de": ["Datum", "Verlikter Standort"],
            "nl": ["Datum", "Locatie leuk gevonden"],
        },
        locale,
    )

    results = []

    for story in stories_created_json.get("ig_stories", []):
        date = epoch_to_date(story.get("creation_timestamp", ""))
        has_latitude_data = any(
            "latitude" in exif_data
            for exif_data in story.get("media_metadata", {})
            .get("photo_metadata", {})
            .get("exif_data", [])
        )

        results.append(
            {
                tl_value[0]: date,
                tl_value[1]: translate("dummy", locale, has_latitude_data),
            }
        )

    stories_df = pd.DataFrame(results)

    return stories_df


def extract_reels_created(reels_created_json, locale):
    """extract your_instagram_activity/content/reels -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {"en": "Count of reels", "de": "Anzahl der Reels", "nl": "Aantal reels"}, locale
    )

    dates = [
        epoch_to_date(media.get("creation_timestamp"))
        for reel in reels_created_json.get("ig_reels_media", [])
        for media in reel.get("media", [])
    ]
    dates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = dates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_followers_new(followers_new_json, locale):
    """extract connections/followers_and_following/followers_1 -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of followers",
            "de": "Anzahl der Follower",
            "nl": "Aantal volgers",
        },
        locale,
    )

    # file can just be dict and not list if only one follower
    if isinstance(followers_new_json, dict):
        dates = [epoch_to_date(followers_new_json["string_list_data"][0]["timestamp"])]
    else:
        dates = [
            epoch_to_date(t["string_list_data"][0]["timestamp"])
            for t in followers_new_json
        ]

    dates_df = pd.DataFrame(dates, columns=[tl_date])  # convert to df

    aggregated_df = dates_df.groupby([tl_date])[
        tl_date
    ].size()  # count number of rows per day

    return aggregated_df.reset_index(name=tl_value)


def extract_search_history(search_history_json, locale):
    """extract logged_information/recent_searches/word_or_phrase_searches -> count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of searches",
            "de": "Anzahl der Suchen",
            "nl": "Aantal zoekopdrachten",
        },
        locale,
    )

    # Extract timestamps
    timestamps = []
    for search in search_history_json.get("searches_keyword", []):
        timestamp_key = None

        # Find the timestamp key
        for key in search["string_map_data"]:
            if "Datum" in key or "Date" in key or "Time" in key:  # language sensitive
                timestamp_key = key
                break

        if timestamp_key and "timestamp" in search["string_map_data"][timestamp_key]:
            timestamps.append(search["string_map_data"][timestamp_key]["timestamp"])

        # Convert timestamps to dates
    dates = [epoch_to_date(t) for t in timestamps]

    # Create DataFrame
    if dates:
        search_df = pd.DataFrame(dates, columns=[tl_date])

        # Count searches per day
        aggregated_df = (
            search_df.groupby([tl_date])[tl_date].size().reset_index(name=tl_value)
        )

        return aggregated_df

    # Return empty DataFrame if no searches found
    return pd.DataFrame(columns=[tl_date, tl_value])


def extract_messages(combined_messages_data, locale):
    """
    Extract message counts per day from all Instagram conversations.

    This function processes the combined messages data structure that contains
    messages from all conversations in the Instagram data export.
    """

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Count of outgoing messages",
            "de": "Anzahl der gesendeten Nachrichten",
            "nl": "Aantal verzonden berichten",
        },
        locale,
    )

    # Process all messages
    message_counts = {}

    # Check if we have the combined messages data structure
    if combined_messages_data and "combined_messages" in combined_messages_data:
        for message in combined_messages_data["combined_messages"]:
            # Convert timestamp (milliseconds) to date
            date = epoch_to_date(
                message["timestamp_ms"] // 1000
            )  # Divide by 1000 to convert ms to seconds

            # Increment count for this date
            if date in message_counts:
                message_counts[date] += 1
            else:
                message_counts[date] = 1

    # Convert to DataFrame
    if message_counts:
        dates = list(message_counts.keys())
        counts = list(message_counts.values())
        result_df = pd.DataFrame({tl_date: dates, tl_value: counts})
        result_df = result_df.sort_values(by=tl_date).reset_index(drop=True)
        return result_df

    # Return empty DataFrame if no messages found
    return pd.DataFrame(columns=[tl_date, tl_value])


def extract_contact_syncing(contact_syncing_json, locale):
    """extract personal_information/personal_information/account_information -> dummy whether 'contact_syncing' is enabled"""

    tl_value = translate(
        {
            "en": "Contact syncing enabled",
            "de": "Kontaktsynchronisierung aktiviert",
            "nl": "Contact synchronisatie ingeschakeld",
        },
        locale,
    )

    value = None

    for k in [
        "Contact Syncing",
        "Kontaktsynchronisierung",
        "Synchronisation des contacts",
    ]:  # keys are language specific
        if k in contact_syncing_json["profile_account_insights"][0]["string_map_data"]:
            value = contact_syncing_json["profile_account_insights"][0][
                "string_map_data"
            ][k]["value"]
            break

    return pd.DataFrame([translate("dummy", locale, value)], columns=[tl_value])


def extract_personal_information(personal_information_json, locale):
    """
    extract personal_information/personal_information/personal_information.json -> dummies whether user has email, phone, and private account
    """

    tl_value = translate(
        {
            "en": [
                "Email",
                "Phone",
                "Private account",
            ],
            "de": [
                "Email",
                "Telefon",
                "Privates Konto",
            ],
            "nl": [
                "Email",
                "Telefoon",
                "Privé-account",
            ],
        },
        locale,
    )

    # check if information present
    email, phone, private_account = None, None, None

    for k in ["Email", "E-Mail-Adresse"]:  # keys are language specific
        if k in personal_information_json["profile_user"][0]["string_map_data"]:
            email = (
                personal_information_json["profile_user"][0]["string_map_data"][k][
                    "value"
                ]
                != "False"
            )
            break

    for k in [
        "Phone Confirmed",
        "Telefonnummer best\u00c3\u00a4tigt",
    ]:  # keys are language specific
        if k in personal_information_json["profile_user"][0]["string_map_data"]:
            phone = (
                personal_information_json["profile_user"][0]["string_map_data"][k][
                    "value"
                ]
                != "False"
            )
            break

    for k in ["Private Account", "Privates Konto"]:  # keys are language specific
        if k in personal_information_json["profile_user"][0]["string_map_data"]:
            private_account = personal_information_json["profile_user"][0][
                "string_map_data"
            ][k]["value"]
            break

    result = pd.DataFrame(
        {
            tl_value[0]: [translate("dummy", locale, email)],
            tl_value[1]: [translate("dummy", locale, phone)],
            tl_value[2]: [translate("dummy", locale, private_account)],
        }
    )

    return result


def extract_topic_interests(topic_interests_json, locale):
    """extract preferences/your_topics -> list of topics"""

    tl_value = translate(
        {"en": "Your topics", "de": "Ihre Themen", "nl": "Uw onderwerpen"}, locale
    )
    topics_list = [
        t["string_map_data"]["Name"]["value"]
        for t in topic_interests_json["topics_your_topics"]
    ]
    topics_df = pd.DataFrame(topics_list, columns=[tl_value])

    return topics_df


def extract_login_activity(login_activity_json, locale):
    """extract security_and_login_information/login_and_account_creation/login_activity -> time and user agent"""

    tl_date = translate("date", locale)
    tl_value1 = translate({"en": "Time", "de": "Uhrzeit", "nl": "Tijd"}, locale)
    tl_value2 = translate(
        {"en": "User agent", "de": "Gerät", "nl": "Gebruikersagent"}, locale
    )

    logins = login_activity_json["account_history_login_history"]

    timestamps = [t["title"] for t in logins]
    dates = [str(datetime.fromisoformat(timestamp).date()) for timestamp in timestamps]
    times = [datetime.fromisoformat(timestamp).time() for timestamp in timestamps]

    user_agents = [t["string_map_data"]["User Agent"]["value"] for t in logins]

    login_df = pd.DataFrame({tl_date: dates, tl_value1: times, tl_value2: user_agents})

    return login_df


def extract_logout_activity(logout_activity_json, locale):
    """extract security_and_login_information/login_and_account_creation/logout_activity -> time and user agent"""

    tl_date = translate("date", locale)
    tl_value1 = translate({"en": "Time", "de": "Uhrzeit", "nl": "Tijd"}, locale)
    tl_value2 = translate(
        {"en": "User agent", "de": "Gerät", "nl": "Gebruikersagent"}, locale
    )

    logouts = logout_activity_json["account_history_logout_history"]

    timestamps = [t["title"] for t in logouts]
    dates = [str(datetime.fromisoformat(timestamp).date()) for timestamp in timestamps]
    times = [datetime.fromisoformat(timestamp).time() for timestamp in timestamps]

    user_agents = [t["string_map_data"]["User Agent"]["value"] for t in logouts]

    logout_df = pd.DataFrame({tl_date: dates, tl_value1: times, tl_value2: user_agents})

    return logout_df
