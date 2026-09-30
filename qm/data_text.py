"""Text building blocks for synthetic Quote Memory data.

All names, companies, emails and notes in this module are FICTIONAL and
SYNTHETIC. They were written for a hackathon prototype about a fictional
Iowa fab shop (Boone Creek Fabrication). Any resemblance to real people or
companies is coincidental.

RFQ_EMAIL_TEMPLATES use str.format with these named placeholders only:
{contact}, {customer}, {part_number}, {part_desc}, {material_text}, {qty},
{finish_text}, {due_text}, {weld_text}. Every template uses {part_number},
{part_desc} and {qty}; the others are optional and each appears at most once.
{due_text} always follows a label (e.g. "Due: "), so a date like "11/14" or a
phrase like "4 weeks ARO" both read naturally.
"""

RFQ_EMAIL_TEMPLATES = [
    # 1. terse
    "Need price on attached, {qty} pcs {part_number} ({part_desc}).\n"
    "Material: {material_text}. Finish: {finish_text}.\n"
    "Due: {due_text}\n"
    "\n"
    "{contact}\n"
    "{customer}",
    # 2. polite
    "Hello,\n"
    "\n"
    "Could you please quote {qty} pieces of {part_number}, {part_desc}, per the attached drawing?\n"
    "Material: {material_text}\n"
    "Finish: {finish_text}\n"
    "Welding: {weld_text}\n"
    "Required delivery: {due_text}\n"
    "\n"
    "Thanks,\n"
    "{contact}\n"
    "{customer}",
    # 3. bare list
    "RFQ - {part_number} {part_desc}\n"
    "Qty: {qty}\n"
    "Matl: {material_text}\n"
    "Weld: {weld_text}\n"
    "Finish: {finish_text}\n"
    "Ship date: {due_text}\n"
    "\n"
    "{contact} / {customer}",
    # 4. friendly
    "Hi,\n"
    "\n"
    "New part coming up, please quote {qty} pcs of {part_number} ({part_desc}). Drawing attached.\n"
    "Material is {material_text}, finish is {finish_text}. Note on welding: {weld_text}.\n"
    "Delivery: {due_text}\n"
    "\n"
    "Thanks much,\n"
    "{contact}\n"
    "{customer}",
    # 5. short, material and finish left to the print
    "Quote needed on {part_number} - {part_desc}, qty {qty}.\n"
    "Material and finish per print. Note: {weld_text}.\n"
    "Timing: {due_text}\n"
    "Please send price and lead time.\n"
    "\n"
    "{contact}\n"
    "{customer}",
    # 6. formal
    "Good morning,\n"
    "\n"
    "We are requesting a quote for the following:\n"
    "\n"
    "Part number: {part_number}\n"
    "Description: {part_desc}\n"
    "Quantity: {qty}\n"
    "Material: {material_text}\n"
    "Finish: {finish_text}\n"
    "Weld requirement: {weld_text}\n"
    "Required date: {due_text}\n"
    "\n"
    "Please include lead time with your quote.\n"
    "\n"
    "Regards,\n"
    "{contact}\n"
    "{customer}",
    # 7. terse, abbreviated
    "Pls quote {qty} ea {part_number} {part_desc}, material {material_text}, finish {finish_text}.\n"
    "Heads up on welds: {weld_text}.\n"
    "Due: {due_text}\n"
    "\n"
    "{contact}\n"
    "{customer}",
    # 8. no date given
    "Hi,\n"
    "\n"
    "Attached is a new drawing for {part_number} ({part_desc}). Looking for pricing on a quantity of {qty}.\n"
    "Material: {material_text}\n"
    "Welds: {weld_text}\n"
    "Finish: {finish_text}\n"
    "\n"
    "Let me know if you have any questions on the print.\n"
    "\n"
    "Thanks,\n"
    "{contact}\n"
    "{customer}",
    # 9. very terse
    "{part_number} / {part_desc} / qty {qty}\n"
    "{material_text}, {finish_text}\n"
    "Delivery: {due_text}\n"
    "Quote pls.\n"
    "\n"
    "{contact}\n"
    "{customer}",
    # 10. polite, longer
    "Hello,\n"
    "\n"
    "We are sourcing a new part, {part_number} ({part_desc}), and would appreciate a quote for {qty} pieces.\n"
    "Material is {material_text} and the finish is {finish_text}.\n"
    "Please pay attention to the welding note: {weld_text}.\n"
    "Requested delivery: {due_text}\n"
    "\n"
    "Please let me know if you need a model or have questions.\n"
    "\n"
    "Thank you,\n"
    "{contact}\n"
    "{customer}",
]

CONTACT_NAMES = [
    "Dana Kessler",
    "Mark Holloway",
    "Jenna Pruitt",
    "Travis Lindgren",
    "Carla Voss",
    "Brent Ostrander",
    "Megan Tolliver",
    "Scott Dreyer",
    "Kelsey Amundsen",
    "Ryan Pettibone",
    "Laura Kinsella",
    "Derek Halvorsen",
    "Nicole Brandvold",
    "Greg Stuckey",
]

WELD_TEXT = {
    "cosmetic": [
        "cosmetic welds on the visible side, no spatter",
        "show-side welds need to be smooth and blended, appearance is inspected",
        "visible welds must look clean, no spatter or undercut on the outside face",
    ],
    "standard": [
        "standard structural welds per print",
        "welds per print, appearance not critical",
        "standard welds, no cosmetic requirement",
    ],
}

FINISH_TEXT = {
    "powder_coat": [
        "powder coat black",
        "powder coat gloss black, mask threads",
        "powder coat safety yellow",
    ],
    "zinc": [
        "zinc plated, clear",
        "zinc plate",
        "yellow zinc",
    ],
    "none": [
        "bare / oiled",
        "no finish, bare steel",
        "raw, light oil for shipping",
    ],
}

TYPO_SWAPS = [
    ("quote", "qoute"),
    ("please", "plese"),
    ("pieces", "peices"),
    ("attached", "attahced"),
    ("drawing", "drawnig"),
    ("delivery", "delivey"),
    ("material", "materail"),
    ("finish", "finsh"),
    ("quantity", "quanity"),
    ("questions", "quesitons"),
    ("appreciate", "apreciate"),
    ("welding", "weldng"),
]

GENERIC_DEBRIEFS = [
    "Ran clean, shipped a day early.",
    "No issues, hours came in right about where we quoted.",
    "Plate showed up late from the supplier, lost two days waiting on material.",
    "Repeat job, nothing new to report.",
    "First piece passed inspection and the rest of the run went smooth.",
    "Split the order across two shifts, no quality problems.",
    "Paint came back on time and parts looked good.",
    "Customer changed a hole location mid-run, updated print is in the job folder.",
    "Short run, most of the time was setup.",
    "Brake was down half a day for maintenance, caught up on 2nd shift.",
    "Shipped complete, counts verified at pack.",
    "Hrs came in slightly under quote on this one, crew did a good job.",
]
