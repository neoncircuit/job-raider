"""Synthetic profiles of the Step 3.4 ranking set (no personal data)."""

from typing import Any, Dict


def skill(name: str, category: str, proficiency: str, years: float) -> Dict[str, Any]:
    """
    One profile skill.

    Args:
        name: The skill name.
        category: A ``SkillCategory`` value.
        proficiency: A ``ProficiencyLevel`` value.
        years: Years of use.

    Returns:
        The skill as a dictionary.
    """
    return {
        "name": name,
        "category": category,
        "proficiency": proficiency,
        "years_of_experience": years,
    }


FRESH_ML: Dict[str, Any] = {
    "name": "Rina Tan",
    "contact": {"email": "rina.tan@example.com", "location": "Singapore"},
    "summary": (
        "Computer science graduate who builds machine learning and retrieval "
        "applications in Python, from data preparation to a small API."
    ),
    "skills": [
        skill("Python", "programming_language", "Advanced", 4.0),
        skill("PyTorch", "framework", "Intermediate", 2.0),
        skill("scikit-learn", "framework", "Intermediate", 2.0),
        skill("Pandas", "framework", "Advanced", 3.0),
        skill("SQL", "programming_language", "Intermediate", 2.0),
        skill("FastAPI", "framework", "Intermediate", 1.0),
        skill("LangChain", "framework", "Intermediate", 1.0),
        skill("Hugging Face Transformers", "framework", "Intermediate", 1.0),
        skill("Docker", "tool", "Beginner", 1.0),
        skill("Git", "tool", "Intermediate", 3.0),
        skill("Machine Learning", "domain", "Intermediate", 2.0),
        skill("Natural Language Processing", "domain", "Intermediate", 1.0),
    ],
    "core_skills": ["Python", "PyTorch", "Machine Learning", "SQL"],
    "experience": [
        {
            "title": "Data Science Intern",
            "company": "Harbourline Logistics",
            "location": "Singapore",
            "start_date": "2024-05-01T00:00:00",
            "end_date": "2024-11-01T00:00:00",
            "current": False,
            "description": "Built demand forecasts for the warehouse planning team.",
            "highlights": [
                "Built a gradient boosting forecast in scikit-learn for weekly parcel volume.",
                "Cleaned two years of shipment records in Pandas and SQL.",
            ],
            "technologies": ["Python", "scikit-learn", "Pandas", "SQL"],
        }
    ],
    "projects": [
        {
            "name": "Course Notes Assistant",
            "description": (
                "A retrieval-augmented question answering app over lecture notes."
            ),
            "technologies": ["Python", "LangChain", "FAISS", "FastAPI"],
            "start_date": "2025-01-01T00:00:00",
            "end_date": "2025-04-01T00:00:00",
            "highlights": [
                "Indexed 400 pages of notes and answered questions with source links."
            ],
            "role": "Developer",
        },
        {
            "name": "Plant Disease Classifier",
            "description": "An image classifier for leaf diseases, trained in PyTorch.",
            "technologies": ["Python", "PyTorch"],
            "start_date": "2024-08-01T00:00:00",
            "end_date": "2024-12-01T00:00:00",
            "highlights": ["Reached 91% accuracy on a held-out set of 2,000 images."],
            "role": "Developer",
        },
        {
            "name": "Review Sentiment Tagger",
            "description": (
                "A fine-tuned transformer that tags product reviews by sentiment."
            ),
            "technologies": ["Python", "Hugging Face Transformers"],
            "start_date": "2025-02-01T00:00:00",
            "end_date": "2025-05-01T00:00:00",
            "highlights": ["Fine-tuned a small BERT model on 20,000 labeled reviews."],
            "role": "Developer",
        },
    ],
    "education": [
        {
            "degree": "Bachelor of Computing in Computer Science",
            "school": "Fictional Marina University",
            "end_date": "2025-06-01T00:00:00",
            "coursework": ["Machine Learning", "Databases", "Data Structures"],
        }
    ],
    "certifications": [],
    "targets": {
        "keywords": ["machine learning engineer", "data scientist", "AI"],
        "locations": ["Singapore"],
        "experience_levels": ["Entry Level"],
        "remote_preference": True,
    },
}

MID_BACKEND: Dict[str, Any] = {
    "name": "Daniel Ong",
    "contact": {"email": "daniel.ong@example.com", "location": "Singapore"},
    "summary": (
        "Backend engineer with four years of experience building Java and Go "
        "services, event pipelines, and the platforms that run them."
    ),
    "skills": [
        skill("Java", "programming_language", "Advanced", 4.0),
        skill("Spring Boot", "framework", "Advanced", 4.0),
        skill("Go", "programming_language", "Intermediate", 2.0),
        skill("PostgreSQL", "database", "Advanced", 4.0),
        skill("Redis", "database", "Intermediate", 3.0),
        skill("Kafka", "tool", "Intermediate", 2.0),
        skill("Docker", "tool", "Advanced", 4.0),
        skill("Kubernetes", "tool", "Intermediate", 2.0),
        skill("AWS", "cloud", "Intermediate", 3.0),
        skill("gRPC", "framework", "Intermediate", 2.0),
        skill("REST APIs", "domain", "Advanced", 4.0),
    ],
    "core_skills": ["Java", "Spring Boot", "Go", "PostgreSQL", "Kafka"],
    "experience": [
        {
            "title": "Software Engineer",
            "company": "Crestpay",
            "location": "Singapore",
            "start_date": "2020-07-01T00:00:00",
            "end_date": "2022-12-01T00:00:00",
            "current": False,
            "description": "Built payment services for merchant onboarding.",
            "highlights": [
                "Built Spring Boot services for merchant checks on PostgreSQL.",
                "Moved nightly batch jobs to Kafka consumers.",
            ],
            "technologies": ["Java", "Spring Boot", "PostgreSQL", "Kafka"],
        },
        {
            "title": "Backend Engineer",
            "company": "Tidewater Freight",
            "location": "Singapore",
            "start_date": "2023-01-01T00:00:00",
            "end_date": "2025-01-01T00:00:00",
            "current": False,
            "description": "Built shipment tracking services and their platform.",
            "highlights": [
                "Wrote Go services with gRPC for shipment events.",
                "Ran the services on Kubernetes in AWS with Redis caching.",
            ],
            "technologies": ["Go", "gRPC", "Kubernetes", "AWS", "Redis", "Docker"],
        },
    ],
    "projects": [
        {
            "name": "Event Replay Tool",
            "description": "A command-line tool that replays Kafka events into a test cluster.",
            "technologies": ["Go", "Kafka"],
            "start_date": "2024-03-01T00:00:00",
            "end_date": "2024-06-01T00:00:00",
            "highlights": ["Cut the time to reproduce a production bug from days to hours."],
            "role": "Developer",
        }
    ],
    "education": [
        {
            "degree": "Bachelor of Engineering in Computer Engineering",
            "school": "Fictional Kallang Institute of Technology",
            "end_date": "2020-06-01T00:00:00",
        }
    ],
    "certifications": [],
    "targets": {
        "keywords": ["backend engineer", "platform engineer", "Java"],
        "locations": ["Singapore"],
        "experience_levels": ["Mid Level"],
        "remote_preference": True,
    },
}

PROFILES: Dict[str, Dict[str, Any]] = {"fresh_ml": FRESH_ML, "mid_backend": MID_BACKEND}

# The matcher settings that the pipeline uses for each profile.
MODES: Dict[str, Dict[str, bool]] = {
    "fresh_ml": {"fresh_grad_mode": True},
    "mid_backend": {"fresh_grad_mode": False},
}
