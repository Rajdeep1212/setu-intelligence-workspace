"""
Eligibility seed data — Week 3.

Hand-entered starter data for the check_eligibility tool. Populate this by
reading the actual scheme guidelines (usually a PIB release or a
myScheme.gov.in page) and encoding the real criteria — the three rows below
are illustrative placeholders, not verified figures. Don't ship these as-is;
verify against the current official guidelines before relying on them for
real eligibility answers.

Run with: python -m ingestion.seed_eligibility
"""

from __future__ import annotations

import asyncio
import json

from ingestion.db_writer import get_pool

SEED_SCHEMES = [
    {
        "scheme_name": "PM Kisan Samman Nidhi",
        "criteria": {
            "description": "Income support for landholding farmer families.",
            "max_landholding": "no upper limit as of latest guidelines — verify",
            "excluded_categories": ["income tax payers", "institutional landholders"],
            "benefit": "Rs 6000/year in three installments",
        },
    },
    {
        "scheme_name": "Pradhan Mantri Jan Dhan Yojana",
        "criteria": {
            "description": "Zero-balance bank account scheme for financial inclusion.",
            "min_age": 10,
            "documents_required": ["Aadhaar or any valid ID proof"],
            "benefit": "Zero-balance account, RuPay card, accident insurance cover",
        },
    },
    {
        "scheme_name": "National Scholarship Portal — Post-Matric Scholarship",
        "criteria": {
            "description": "Scholarship for post-matric students from specified categories.",
            "max_family_income": 250000,
            "eligible_categories": ["SC", "ST", "OBC", "minority", "as per current guidelines"],
            "benefit": "Tuition fee reimbursement + maintenance allowance",
        },
    },
]


async def seed() -> None:
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            for scheme in SEED_SCHEMES:
                await conn.execute(
                    """
                    INSERT INTO eligibility_criteria (scheme_name, criteria)
                    VALUES ($1, $2::jsonb)
                    ON CONFLICT (scheme_name) DO UPDATE SET
                        criteria = EXCLUDED.criteria
                    """,
                    scheme["scheme_name"],
                    json.dumps(scheme["criteria"]),
                )
        print(f"Seeded {len(SEED_SCHEMES)} eligibility rows.")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(seed())
