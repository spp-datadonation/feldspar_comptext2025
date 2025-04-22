from port.api.assets import *
from port.api.props import Translatable
import pandas as pd
from datetime import datetime, timezone, timedelta
import re
import json

############################
# Helper functions for extraction
############################


def translate(value, locale, dummy_decider=None):
    """Translate outputs"""
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
# Extraction functions for YouTube data
############################


def extract_watch_history(watch_history_json, locale):
    """Extract YouTube watch history with date, time, title, channel, and URL"""

    tl_date = translate("date", locale)
    tl_time = translate(
        {
            "en": "Time",
            "de": "Zeit",
            "nl": "Tijd",
        },
        locale,
    )
    tl_title = translate(
        {
            "en": "Video Title",
            "de": "Video-Titel",
            "nl": "Video Titel",
        },
        locale,
    )
    tl_channel = translate(
        {
            "en": "Channel",
            "de": "Kanal",
            "nl": "Kanaal",
        },
        locale,
    )
    tl_url = translate(
        {
            "en": "URL",
            "de": "URL",
            "nl": "URL",
        },
        locale,
    )

    # Initialize list to store watch history entries
    results = []

    # Process each entry in the watch history
    for entry in watch_history_json:
        if "time" in entry and "titleUrl" in entry:  # Make sure it's a video entry
            # Extract date and time from ISO timestamp
            datetime_str = entry["time"]
            date_str = datetime_str.split("T")[0]
            time_str = datetime_str.split("T")[1].split(".")[0]  # Extract HH:MM:SS

            # Get title (remove "Watched " prefix if present)
            title = entry.get("title", "Unknown")
            if title.startswith("Watched "):
                title = title[8:]

            # Get URL
            url = entry.get("titleUrl", "Unknown")

            # Get channel name if available
            channel = "Unknown"
            if "subtitles" in entry and len(entry["subtitles"]) > 0:
                channel = entry["subtitles"][0].get("name", "Unknown")

            results.append(
                {
                    "date": date_str,
                    "time": time_str,
                    "title": title,
                    "channel": channel,
                    "url": url,
                }
            )

    if not results:
        return pd.DataFrame(
            {
                tl_date: ["N/A"],
                tl_time: ["N/A"],
                tl_title: ["No watch history found"],
                tl_channel: ["N/A"],
                tl_url: ["N/A"],
            }
        )

    # Create DataFrame with all the information
    watch_df = pd.DataFrame(results)
    watch_df.columns = [tl_date, tl_time, tl_title, tl_channel, tl_url]

    return watch_df


def extract_comments(comments_csv, locale):
    """Extract YouTube comment history and count per day"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Number of comments",
            "de": "Anzahl der Kommentare",
            "nl": "Aantal reacties",
        },
        locale,
    )

    # Find the date column
    date_column = None
    for possible_column in [
        "Zeitstempel der Erstellung des Kommentars",
        "Comment Create Timestamp",
    ]:  # language sensitive
        if possible_column in comments_csv.columns:
            date_column = possible_column
            break

    if date_column is None:
        return pd.DataFrame(
            {
                tl_date: ["N/A"],
                tl_value: [f"Total comments: {len(comments_csv)}"],
            }
        )

    # Convert dates to a consistent format
    comments_csv[date_column] = pd.to_datetime(
        comments_csv[date_column], errors="coerce"
    )
    # Extract just the date portion (without time)
    comments_csv["formatted_date"] = comments_csv[date_column].dt.strftime("%Y-%m-%d")

    # Remove entries with NaT values
    comments_csv = comments_csv.dropna(subset=["formatted_date"])

    # Count comments per day
    daily_counts = (
        comments_csv.groupby("formatted_date").size().reset_index(name=tl_value)
    )
    daily_counts.rename(columns={"formatted_date": tl_date}, inplace=True)

    return daily_counts


def extract_subscriptions(subscriptions_csv, locale):
    """Extract YouTube channel subscriptions"""

    # Define column name
    if "Kanaltitel" in subscriptions_csv.columns:  # language sensitive
        channel_column = "Kanaltitel"
    else:
        channel_column = "Channel Title"

    tl_channel = translate(
        {
            "en": "Subscribed Channel",
            "de": "Abonnierter Kanal",
            "nl": "Geabonneerd kanaal",
        },
        locale,
    )

    # Create DataFrame with just the channel names
    subscriptions_df = pd.DataFrame({tl_channel: subscriptions_csv[channel_column]})

    return subscriptions_df


def extract_search_history(search_history_json, locale):
    """Extract YouTube search history with search terms"""

    tl_date = translate("date", locale)
    tl_value = translate(
        {
            "en": "Search term",
            "de": "Suchbegriff",
            "nl": "Zoekterm",
        },
        locale,
    )

    # Initialize lists to store results
    results = []

    # Process each entry in the search history
    for entry in search_history_json:
        if "time" in entry:  # Make sure it has a timestamp
            # Extract date (YYYY-MM-DD) from ISO timestamp
            date_str = entry["time"].split("T")[0]

            # Extract search term
            search_term = "Unknown"
            if "title" in entry:
                title = entry["title"]
                if title.startswith("Searched for "):
                    search_term = title[13:]
                else:
                    search_term = title

            results.append({"date": date_str, "search_term": search_term})

    if not results:
        return pd.DataFrame(
            {
                tl_date: ["N/A"],
                tl_value: ["No valid search terms found"],
            }
        )

    # Create DataFrame with search terms
    search_df = pd.DataFrame(results)
    search_df.columns = [tl_date, tl_value]

    return search_df
