"""Established public health knowledge, deliberately kept apart from our measurements.

This project measured overnight heat exposure in Phoenix and found, among other
things, that it cannot support any claim about how much cooling an intervention
would buy. That is a real limit and the agent must respect it.

It is a different question entirely from "why does overnight heat harm people"
and "what do cities normally do about it". Those are well established in the
epidemiological and public health literature, and refusing to answer them would
leave a non-specialist reader with a map they cannot interpret.

So the two kinds of knowledge live in separate tools with separate provenance.
Everything in this module is marked as general literature rather than a finding
of this study, and none of it is tied to a specific tract or a predicted effect.
The agent is instructed to keep the distinction visible in its answers.
"""
from __future__ import annotations

PROVENANCE = (
    "General public health literature, not measured in this study. "
    "Applies to overnight heat broadly and says nothing about how any specific "
    "Phoenix tract would respond to any specific intervention."
)


def why_night_heat_matters() -> dict:
    """Plain-language mechanism: why the overnight low matters more than the peak."""
    return {
        "provenance": PROVENANCE,
        "short_answer": (
            "The body sheds accumulated heat during the cooler part of the day. When "
            "the night stays hot, that recovery period never arrives, and the strain "
            "from the previous day carries into the next one."
        ),
        "mechanism": [
            "Cooling the body relies on radiating heat to air that is cooler than skin. "
            "Once air temperature stays close to skin temperature, that route narrows and "
            "sweating is left to do the work.",
            "Sweating costs fluid and puts sustained load on the heart and circulation. "
            "A night that never cools means that load does not let up.",
            "Sleep is disrupted well before temperatures become dangerous, which "
            "compounds the strain across a multi-day heat event.",
            "Indoor temperature lags outdoor temperature. A building that absorbed heat "
            "all day keeps releasing it inside for hours after the outside air drops, so "
            "the indoor overnight low is generally worse than the outdoor reading.",
        ],
        "why_epidemiologists_watch_the_minimum": (
            "Overnight minimum temperature is a better predictor of heat-related death "
            "than the daytime maximum. Multi-day events are more lethal than single hot "
            "days for the same reason: the deficit accumulates when nights do not clear."
        ),
        "who_is_most_at_risk": [
            "People over 65, whose thermoregulation and thirst response are reduced.",
            "People with cardiovascular or respiratory conditions, where the extra "
            "circulatory load matters most.",
            "People taking medications that affect sweating, fluid balance or heart rate.",
            "People without air conditioning, or with it but unable to afford to run it "
            "overnight, which is the more common situation.",
            "People living alone or socially isolated, who may not be found in time.",
            "People in housing with little thermal mass or insulation, where indoor "
            "temperature tracks and amplifies the outdoor night.",
        ],
    }


def what_cities_do() -> dict:
    """The standard heat-response playbook, with the honest caveat attached."""
    return {
        "provenance": PROVENANCE,
        "important_caveat": (
            "These are the measures heat-response programmes commonly use. This study did "
            "NOT measure how much any of them would change overnight temperature, and "
            "found no detectable link between surface composition and overnight exposure "
            "once position was accounted for. Treat this as the standard menu, not as a "
            "prediction of results."
        ),
        "immediate_operational": [
            {
                "action": "Extend cooling centre hours into the night",
                "why": (
                    "Most cooling centres close in the evening, which is before the risk "
                    "period this data describes begins."
                ),
                "timescale": "days",
            },
            {
                "action": "Welfare checks on isolated at-risk residents",
                "why": "Isolation is a repeated factor in indoor heat deaths.",
                "timescale": "days",
            },
            {
                "action": "Suspend utility disconnection during heat events",
                "why": (
                    "Air conditioning only helps if the power stays on and the household "
                    "is not avoiding use out of cost fear."
                ),
                "timescale": "policy, immediate",
            },
            {
                "action": "Targeted energy bill assistance",
                "why": (
                    "Having a unit and being able to run it overnight are different "
                    "things, and the second is the binding constraint for many households."
                ),
                "timescale": "weeks",
            },
        ],
        "longer_term_built_environment": [
            {
                "action": "Cool or reflective roofing and pavement",
                "why": "Reduces daytime heat absorbed and re-radiated after dark.",
                "timescale": "years",
                "evidence_note": (
                    "Widely used, including Phoenix's own cool pavement programme. Our "
                    "measurements could not detect a surface-composition effect on "
                    "overnight exposure independent of position, so we make no claim "
                    "about the size of the benefit here."
                ),
            },
            {
                "action": "Tree canopy and shade structures",
                "why": "Reduces daytime surface heating and improves daytime comfort.",
                "timescale": "years",
                "evidence_note": (
                    "Better established for daytime conditions than for overnight "
                    "minima. Vegetation did not survive our controls either."
                ),
            },
            {
                "action": "Housing retrofits: insulation, ventilation, efficient cooling",
                "why": (
                    "Acts on the indoor night temperature, which is what people are "
                    "actually exposed to while asleep."
                ),
                "timescale": "years",
            },
        ],
        "what_measurement_like_this_is_actually_for": (
            "Deciding where to send a finite number of welfare checks and which "
            "neighbourhoods to keep a cooling centre open in. It narrows a citywide "
            "problem to a list of places, which is a different job from proving that a "
            "particular intervention works."
        ),
    }


def glossary() -> dict:
    """Plain-language definitions for a reader who has not seen this data before."""
    return {
        "provenance": "Definitions of terms used on this page.",
        "terms": {
            "hours above 28 C": (
                "How much of the night, between midnight and dawn, the air outside stayed "
                "above 28 degrees Celsius, about 82 Fahrenheit. Six hours means the whole "
                "window: it never once dropped below that line."
            ),
            "relief hours": (
                "The rest of that window, the part of the night that did get below the "
                "line. Zero relief hours is the worst case."
            ),
            "census tract": (
                "A statistical area of roughly 1,200 to 8,000 residents, used because "
                "population and vulnerability data are published at that level. Roughly "
                "a neighbourhood."
            ),
            "social vulnerability index": (
                "A CDC score from 0 to 1 combining income, age, disability, vehicle "
                "access and similar factors. 0.9 means more vulnerable than 90 percent of "
                "US tracts. Heat programmes often use it to decide where to work."
            ),
            "the targeted band": (
                "The top quarter of the vulnerability index, which is the group a "
                "programme aiming at the most vulnerable places would typically cover."
            ),
            "2 metres above ground": (
                "The standard height for air temperature measurement, roughly head "
                "height, rather than the surface temperature a satellite sees."
            ),
        },
    }


REGISTRY = {
    "why_night_heat_matters": why_night_heat_matters,
    "what_cities_do": what_cities_do,
    "glossary": glossary,
}
