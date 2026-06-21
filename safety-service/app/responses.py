HIGH_EN = (
    "I’m glad you told me. What you’re describing deserves support from a "
    "real person today. Please contact someone you trust and consider "
    "contacting a qualified mental-health professional or crisis service. "
    "If you might act on thoughts of harming yourself or someone else, "
    "contact local emergency services now and move away from anything that "
    "could be used to cause harm. Are you in immediate danger right now?"
)

IMMEDIATE_EN = (
    "I’m concerned that you may be in immediate danger. Contact local "
    "emergency services now or go to the nearest emergency department. "
    "Move away from anything that could be used to cause harm and contact a "
    "trusted person who can stay with you. This chat is not an emergency "
    "service. Are you able to call emergency services or a trusted person now?"
)

HIGH_SR = (
    "Drago mi je što si ovo rekao/la. Ono što opisuješ zaslužuje podršku "
    "stvarne osobe danas. Obrati se nekome kome veruješ i razmisli o kontaktu "
    "sa stručnjakom za mentalno zdravlje ili kriznom službom. Ako postoji "
    "mogućnost da povrediš sebe ili nekog drugog, odmah pozovi lokalnu hitnu "
    "službu i udalji se od svega čime bi mogla nastati povreda. Da li si sada "
    "u neposrednoj opasnosti?"
)

IMMEDIATE_SR = (
    "Zabrinut/a sam da si možda u neposrednoj opasnosti. Odmah pozovi lokalnu "
    "hitnu službu ili idi u najbližu urgentnu službu. Udalji se od svega čime "
    "bi mogla nastati povreda i pozovi osobu od poverenja koja može ostati uz "
    "tebe. Ovaj čet nije hitna služba. Možeš li sada pozvati hitnu službu ili "
    "osobu od poverenja?"
)


def looks_serbian(text: str) -> bool:
    normalized = f" {text.lower()} "
    markers = (
        " č", " ć", " š", " ž", " đ",
        " sam ", " nisam ", " osećam ", " osecam ",
        " želim ", " zelim ", " mogu ", " pomoć ", " pomoc ",
    )
    return any(marker in normalized for marker in markers)


def controlled_response(risk_level: str, message: str) -> str | None:
    serbian = looks_serbian(message)

    if risk_level == "high":
        return HIGH_SR if serbian else HIGH_EN

    if risk_level == "immediate":
        return IMMEDIATE_SR if serbian else IMMEDIATE_EN

    return None
