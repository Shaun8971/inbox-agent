"""Gmail actions: the ONLY module that changes anything in Gmail.

It can do exactly three things to an email: mark as read, archive, and add a label (plus undo them).
There is deliberately no function here that sends, drafts, or deletes email.
"""

SKIPPED_LABEL = "Agent/Skipped"


def get_or_create_label(service, name):
    """Return the ID of a Gmail label, creating the label first if it doesn't exist.
    Gmail actions refer to labels by ID (e.g. Label_123), not by name."""
    existing = service.users().labels().list(userId="me").execute(num_retries=5).get("labels", [])
    for label in existing:
        if label["name"] == name:
            return label["id"]
    # Not found: create it, visible in the left pane and on emails
    body = {"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
    return service.users().labels().create(userId="me", body=body).execute(num_retries=5)["id"]


def skip_email(service, email_id, label_id):
    """Mark as read, archive, and label one email, all in a single Gmail call.
    In Gmail, "read" = removing the UNREAD label, and "archive" = removing the INBOX label."""
    body = {"removeLabelIds": ["UNREAD", "INBOX"], "addLabelIds": [label_id]}
    service.users().messages().modify(userId="me", id=email_id, body=body).execute(num_retries=5)


def undo_skip(service, email_id, label_id):
    """Reverse skip_email: back to unread, back in the inbox, Agent/Skipped label removed."""
    body = {"addLabelIds": ["UNREAD", "INBOX"], "removeLabelIds": [label_id]}
    service.users().messages().modify(userId="me", id=email_id, body=body).execute(num_retries=5)


def apply_actions(service, items, dry_run=True):
    """Carry out the decided action for each item. Only "skip" changes Gmail; act and read leave it untouched.
    dry_run=True (the default) changes nothing and only reports what WOULD happen: shadow mode."""
    label_id = None
    if not dry_run:
        get_or_create_label(service, "Agent")   # The parent label, so Agent/Skipped shows nested under Agent
        label_id = get_or_create_label(service, SKIPPED_LABEL)

    done = []
    for it in items:
        if it["action"] != "skip":
            continue   # Act and Read: stay unread in the inbox, so there's nothing to do
        if not dry_run:
            skip_email(service, it["id"], label_id)
        done.append(it)

    verb = "Would skip" if dry_run else "Skipped"
    print(f"{verb}: {len(done)} of {len(items)} emails")
    return done