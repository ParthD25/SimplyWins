"""Deterministic generator for the support-ticket-routing dataset.

The dataset is synthetic. That is a real limitation, recorded in DATASET.md and
in every run record: difficulty here is a property of this generator, not of
production support traffic. What it does support is a like-for-like comparison
of methods under identical conditions, which is what the benchmark claims.

Difficulty is deliberate. Tickets share vocabulary across classes, some state
one intent while mentioning another, some negate a category, and some are too
short to carry much signal. Without those, keyword matching would score near
100% and the comparison would say nothing.

The train/test split is **template-disjoint**: each class reserves a third of
its phrasings for evaluation only, so no test ticket is a slot-substitution of
a training ticket. A random split over a finite template pool let a character
n-gram model memorise phrasing fingerprints and score 98.75%, which measured
recall of the generator rather than generalisation to unseen wording.

Regenerate with:
    python -m app.benchmarks.datasets.support_ticket_routing.generate
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path

DATASET_NAME = "support-ticket-routing"
DATASET_VERSION = "3.0.0"
GENERATOR_VERSION = "3.0.0"
SEED = 20260830
TOTAL_EXAMPLES = 4000
TRAIN_FRACTION = 0.6

LABELS = ("billing", "technical", "account", "shipping", "other")

DATA_DIR = Path(__file__).parent / "data"
DATASET_PATH = DATA_DIR / f"{DATASET_NAME}.v{DATASET_VERSION}.jsonl"

# Phrasings written as a support agent would see them. Slots in braces are
# filled from the pools below, which overlap across classes on purpose.
TEMPLATES: dict[str, tuple[str, ...]] = {
    "billing": (
        "I was charged {amount} twice this month for my {product}",
        "why has my invoice gone up to {amount}",
        "please refund the {amount} you charged on {date}",
        "the receipt for {date} does not match what left my {payment}",
        "I cancelled last month but you still charged me {amount}",
        "my invoice says {amount} but I was quoted less for the {product}",
        "my {payment} was declined and the {product} now shows unpaid",
        "you billed {amount} after I downgraded, I want a refund",
        "there is a duplicate charge on the invoice from {date}",
        "can someone explain the {amount} line item on my latest invoice",
        "the tax on my invoice looks wrong, I was charged {amount}",
        "I need copies of every invoice since {date} for expenses",
        "we were double billed for the {product} on {date}",
        "the payment for {date} failed but you still charged my {payment}",
        "how do I update the {payment} you charge each month",
        "can I get a refund for the unused part of my {product}",
        "my subscription renewed at {amount} without any warning",
        "the invoice total does not match the price on your site",
        "you charged {amount} for a {product} I never ordered",
        "please stop billing me, I cancelled the {product} on {date}",
        "I paid {amount} on {date} but the invoice still shows unpaid",
        "the refund you promised on {date} has not reached my {payment}",
        "why does my invoice list two charges for the same {product}",
        "our finance team needs a receipt for the {amount} payment",
        "the price of the {product} changed without notice on my invoice",
        "I was billed in the wrong currency, the charge shows {amount}",
        "can you move my billing date, the {amount} always comes out early",
        "the discount was not applied and I was charged full price",
        "I need an invoice addressed to the company, not my {payment}",
        "you took {amount} from my {payment} twice on {date}",
    ),
    "technical": (
        "the {product} crashes every time I open the reports tab",
        "getting a {code} error whenever I try to sync",
        "the page hangs forever after I click save",
        "export produces an empty file since the update on {date}",
        "search returns nothing even though the records are there",
        "the app freezes on the loading screen and never recovers",
        "the api returns {code} errors on roughly half our requests",
        "notifications stopped working after the {date} release",
        "the dashboard shows stale data compared to what we uploaded",
        "uploading anything large fails with a {code} error",
        "the webhook has not fired since {date}, nothing in the logs",
        "everything is timing out this morning, most pages error",
        "the {product} throws a {code} whenever I filter the list",
        "sync has been broken since {date} and shows no error",
        "clicking save does nothing, the console shows a {code}",
        "the import tool crashes halfway through every file",
        "the app is extremely slow since the {date} update",
        "our integration started returning {code} without any change on our side",
        "the report page is blank, it just spins and never loads",
        "the {product} logs me out mid-session with a {code} error",
        "attachments fail to upload and the page freezes",
        "the api documentation example returns a {code} error",
        "charts render empty even though the data loaded fine",
        "the mobile app crashes on launch since {date}",
        "bulk edit times out whenever I select more than a few rows",
        "the {product} shows a {code} error page after login",
        "data stopped syncing and the last update was {date}",
        "the filter is broken, results do not match what I select",
        "every save throws an error but the change appears anyway",
        "the page loads but every button is unresponsive",
    ),
    "account": (
        "I cannot log in, it says my password is wrong",
        "please add {name} to our workspace as an editor",
        "how do I turn on two factor authentication for my login",
        "remove {name} from the team, they have left",
        "I need to change the email address on my account",
        "{name} has admin but my login only shows read access",
        "we want to transfer workspace ownership to {name}",
        "the password reset email never arrives at my address",
        "can you merge my two logins into a single account",
        "I am locked out after too many password attempts",
        "what permissions does the viewer role have on my account",
        "please close my account and remove my data",
        "my login stopped working after I changed my password",
        "{name} needs admin permissions on the workspace",
        "two factor is sending codes to an old phone number",
        "I signed up with the wrong email and need it changed",
        "can you reset the password for {name}, they are locked out",
        "my account shows the wrong role after the last change",
        "how do I remove admin access from {name}",
        "the workspace invite for {name} expired before they could log in",
        "I need to add a second admin to the account in case I am away",
        "logging in redirects me back to the login page every time",
        "please deactivate the login for {name} immediately",
        "my email address changed and now I cannot sign in",
        "we need single sign on for everyone on the account",
        "the permissions for my role changed without anyone editing them",
        "I want to delete my account but keep the workspace for {name}",
        "can {name} have access to the workspace without admin rights",
        "my two factor codes are being rejected at login",
        "how many admins can one workspace account have",
    ),
    "shipping": (
        "my parcel was due {date} and still has not arrived",
        "tracking has said out for delivery since {date}",
        "the box arrived damaged and one item is missing",
        "can I change the delivery address before it ships",
        "do you deliver to {place} and how long does it take",
        "the courier left my parcel with a neighbour",
        "I received the wrong item, I ordered the {product}",
        "how do I return this for an exchange",
        "the tracking number does not work on the carrier site",
        "only half my order arrived, where is the rest",
        "can I get delivery before {date}",
        "my package is stuck in customs in {place}",
        "the order shipped to my old address by mistake",
        "delivery was attempted while I was out, how do I rearrange",
        "my parcel has not moved in tracking since {date}",
        "the courier marked it delivered but nothing arrived",
        "how much does shipping to {place} cost for the {product}",
        "I need to return the {product}, it arrived broken",
        "the delivery estimate keeps moving further out",
        "can you ship the replacement before I return the original",
        "my order says shipped but tracking shows no movement",
        "the parcel was returned to sender, can you resend it",
        "is express delivery available to {place}",
        "the {product} arrived but the packaging was crushed",
        "I missed the delivery, can it be left with a neighbour",
        "the return label you sent will not print",
        "my order was split into two parcels and one is missing",
        "delivery to {place} is showing as unavailable at checkout",
        "the courier needs a signature but nobody is home during the day",
        "can I collect my parcel from the depot instead",
    ),
    "other": (
        "just wanted to say the new design looks great",
        "do you offer a student discount",
        "are you hiring on the support team",
        "can I speak to someone about a partnership",
        "where do I find your press kit",
        "is there a public roadmap anywhere",
        "hello",
        "thanks for the quick reply yesterday",
        "please remove me from your marketing emails",
        "do you have documentation available in {place}",
        "who handles security disclosures",
        "what are your support hours over the holidays",
        "loving the product so far, keep it up",
        "do you have a case study I could share with my team",
        "is there a community forum for users",
        "can I get a demo for my colleagues",
        "what is your uptime commitment",
        "do you sponsor conferences in {place}",
        "who should I contact about press enquiries",
        "is there an affiliate programme",
        "can you send me your accessibility statement",
        "do you have plans for a {place} office",
        "thanks, that resolved it, no further help needed",
        "is there a newsletter I can subscribe to",
        "what is on the roadmap for next quarter",
        "can I suggest a feature somewhere",
        "do you publish an annual report",
        "how do I join the beta programme",
        "your status page has not updated in a while",
        "just checking this address reaches a human",
    ),
}

AMOUNTS = ("$12", "$49", "$120", "$19.99", "£85", "€230", "$1,400")
PRODUCTS = ("pro plan", "team licence", "starter bundle", "annual subscription", "hardware kit")
DATES = ("the 3rd", "last Tuesday", "March 2nd", "the 14th", "yesterday", "last Friday")
PAYMENTS = ("card", "bank account", "paypal", "credit card")
CODES = ("500", "403", "timeout", "502", "connection reset")
NAMES = ("Priya", "Tom", "Alex", "Sam", "Dana")
PLACES = ("Ireland", "Berlin", "Toronto", "Singapore", "Spain")

SLOTS = {
    "amount": AMOUNTS,
    "product": PRODUCTS,
    "date": DATES,
    "payment": PAYMENTS,
    "code": CODES,
    "name": NAMES,
    "place": PLACES,
}

# Openers and closers add length without adding class signal.
OPENERS = (
    "",
    "",
    "",
    "hi, ",
    "hello, ",
    "hi team, ",
    "sorry to bother you but ",
    "quick one — ",
    "urgent: ",
    "following up again, ",
)
CLOSERS = (
    "",
    "",
    "",
    " please advise",
    " can someone help",
    " thanks",
    " this is the second time I've asked",
    " let me know",
    " appreciate any help",
)

# A second clause pulled from another class. The label stays the primary intent,
# so a method keying purely on vocabulary will misroute these.
CROSS_CLAUSES = {
    "billing": (" and my card on file needs updating", " also the invoice pdf will not open"),
    "technical": (
        " and the app crashed while I was checking",
        " also the page errored when I looked",
    ),
    "account": (" and I could not log in to check", " also my login stopped working"),
    "shipping": (" and my order is still not here", " also the tracking page is blank"),
    "other": (" and thanks for the help last time", " also loving the new update"),
}

NEGATIONS = (
    "this is not a {other} question but ",
    "not about {other}, ",
    "unrelated to my {other} issue — ",
)

TYPO_MAP = {"e": "3", "o": "0", "i": "1", "s": "z", "a": "@"}


@dataclass(frozen=True, slots=True)
class GeneratedExample:
    example_id: str
    text: str
    label: str
    split: str
    difficulty: str
    template_id: str


def _fill(template: str, rng: random.Random) -> str:
    text = template
    for slot, pool in SLOTS.items():
        token = "{" + slot + "}"
        while token in text:
            text = text.replace(token, rng.choice(pool), 1)
    return text


def _typo(text: str, rng: random.Random) -> str:
    characters = list(text)
    for index, character in enumerate(characters):
        if character in TYPO_MAP and rng.random() < 0.12:
            characters[index] = TYPO_MAP[character]
    return "".join(characters)


def _make_example(
    index: int,
    label: str,
    rng: random.Random,
    *,
    template_index: int,
    split: str,
) -> GeneratedExample:
    text = _fill(TEMPLATES[label][template_index], rng)
    difficulty = "plain"

    roll = rng.random()
    if roll < 0.15:
        # Multi-intent: mentions a second area, label stays the primary intent.
        other = rng.choice([name for name in LABELS if name != label])
        text += _fill(rng.choice(CROSS_CLAUSES[other]), rng)
        difficulty = "multi_intent"
    elif roll < 0.23:
        other = rng.choice([name for name in LABELS if name != label])
        text = _fill(rng.choice(NEGATIONS).replace("{other}", other), rng) + text
        difficulty = "negation"
    elif roll < 0.33:
        # Sparse: truncate to a handful of words.
        words = text.split()
        text = " ".join(words[: max(2, len(words) // 3)])
        difficulty = "sparse"

    text = rng.choice(OPENERS) + text + rng.choice(CLOSERS)
    if rng.random() < 0.10:
        text = _typo(text, rng)
        difficulty = "typos" if difficulty == "plain" else difficulty
    if rng.random() < 0.5:
        text = text.capitalize()

    return GeneratedExample(
        example_id=f"stk-{index:05d}",
        text=text.strip(),
        label=label,
        split=split,
        difficulty=difficulty,
        template_id=f"{label}-{template_index:02d}",
    )


def split_templates(rng: random.Random) -> dict[str, dict[str, tuple[int, ...]]]:
    """Reserve a third of each class's phrasings for evaluation only.

    Returned as template indices per class per split so the assignment is
    inspectable and recorded alongside every example.
    """
    assignment: dict[str, dict[str, tuple[int, ...]]] = {}
    for label in LABELS:
        indices = list(range(len(TEMPLATES[label])))
        rng.shuffle(indices)
        cutoff = round(len(indices) * TRAIN_FRACTION)
        assignment[label] = {
            "train": tuple(sorted(indices[:cutoff])),
            "test": tuple(sorted(indices[cutoff:])),
        }
    return assignment


def generate() -> list[GeneratedExample]:
    rng = random.Random(SEED)
    assignment = split_templates(rng)

    per_split = {
        "train": round(TOTAL_EXAMPLES * TRAIN_FRACTION),
        "test": TOTAL_EXAMPLES - round(TOTAL_EXAMPLES * TRAIN_FRACTION),
    }

    examples: list[GeneratedExample] = []
    index = 0
    for split, quota in per_split.items():
        for position in range(quota):
            label = LABELS[position % len(LABELS)]
            template_index = rng.choice(assignment[label][split])
            examples.append(
                _make_example(index, label, rng, template_index=template_index, split=split)
            )
            index += 1

    examples.sort(key=lambda item: item.example_id)
    return examples


def write() -> tuple[Path, str, int]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    examples = generate()
    lines = [
        json.dumps(
            {
                "example_id": item.example_id,
                "text": item.text,
                "label": item.label,
                "split": item.split,
                "difficulty": item.difficulty,
                "template_id": item.template_id,
            },
            sort_keys=True,
        )
        for item in examples
    ]
    payload = "\n".join(lines) + "\n"
    DATASET_PATH.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return DATASET_PATH, digest, len(examples)


if __name__ == "__main__":
    path, digest, count = write()
    print(f"wrote {count} examples to {path}")
    print(f"sha256 {digest}")
