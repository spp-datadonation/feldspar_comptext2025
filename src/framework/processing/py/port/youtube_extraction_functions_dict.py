import port.youtube_extraction_functions as ef

# defines which extraction functions are used and what titles are displayed
# patterns are the exact filenames found in the YouTube export

extraction_dict = {
    "watch_history": {
        "extraction_function": ef.extract_watch_history,
        "patterns": ["Wiedergabeverlauf.json", "watch-history.json"],
        "title": {
            "en": "Which videos have you watched on YouTube?",
            "de": "Welche Videos haben Sie auf YouTube angesehen?",
            "nl": "Welke video's heb je bekeken op YouTube?",
        },
    },
    "comments": {
        "extraction_function": ef.extract_comments,
        "patterns": ["Kommentare.csv", "comments.csv"],
        "title": {
            "en": "How many comments have you made per day?",
            "de": "Wie viele Kommentare haben Sie pro Tag geschrieben?",
            "nl": "Hoeveel reacties heb je per dag geplaatst?",
        },
    },
    "subscriptions": {
        "extraction_function": ef.extract_subscriptions,
        "patterns": ["Abos.csv", "subscriptions.csv"],
        "title": {
            "en": "Which channels are you subscribed to?",
            "de": "Welche Kanäle haben Sie abonniert?",
            "nl": "Op welke kanalen ben je geabonneerd?",
        },
    },
    "search_history": {
        "extraction_function": ef.extract_search_history,
        "patterns": ["Suchverlauf.json", "search-history.json"],
        "title": {
            "en": "What have you searched for on YouTube?",
            "de": "Wonach haben Sie auf YouTube gesucht?",
            "nl": "Waar heb je naar gezocht op YouTube?",
        },
    },
}
