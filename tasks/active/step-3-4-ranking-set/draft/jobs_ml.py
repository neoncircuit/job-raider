"""Constructed data, machine learning, and AI jobs of the Step 3.4 ranking set.

Each job has a draft label for each profile: (label, reason). The labels
follow README.md and were written before any ranker ran on the set.
"""

from typing import Any, Dict, List, Sequence, Tuple

Label = Tuple[int, str]


def job(
    number: int,
    title: str,
    company: str,
    level: str,
    description: str,
    labels: Dict[str, Label],
    skills: Sequence[str] = (),
    location: str = "Singapore",
    work_mode: str = "On-site",
    optional_skills: Sequence[str] = (),
) -> Dict[str, Any]:
    """
    One constructed job with its draft labels.

    Args:
        number: The job number (the ID is ``rk-<number>``).
        title: The job title.
        company: A fictional company.
        level: An ``ExperienceLevel`` value.
        description: The job text.
        labels: Profile ID to (label, reason).
        skills: Required skills (empty: the job has only a description).
        location: The location.
        work_mode: A ``WorkMode`` value.
        optional_skills: Skills that are nice to have.

    Returns:
        The job as a dictionary, with a ``labels`` key.
    """
    skill_rows: List[Dict[str, Any]] = [
        {"name": name, "is_required": True} for name in skills
    ] + [{"name": name, "is_required": False} for name in optional_skills]
    return {
        "job_id": f"rk-{number:03d}",
        "title": title,
        "company": company,
        "source": "other",
        "location": location,
        "work_mode": work_mode,
        "is_remote": work_mode == "Remote",
        "experience_level": level,
        "description": " ".join(description.split()),
        "skills": skill_rows,
        "labels": labels,
    }


def both(fresh: Label, mid: Label) -> Dict[str, Label]:
    """
    Labels for the two profiles.

    Args:
        fresh: The label for ``fresh_ml``.
        mid: The label for ``mid_backend``.

    Returns:
        Profile ID to (label, reason).
    """
    return {"fresh_ml": fresh, "mid_backend": mid}


ML_ROLE_FOR_BACKEND: Label = (0, "Machine learning role; not a backend or platform target")

JOBS_ML: List[Dict[str, Any]] = [
    job(
        1,
        "Graduate Machine Learning Engineer",
        "Lumen Analytics",
        "Entry Level",
        """Join our applied machine learning team as a graduate engineer. You will
        train and evaluate models in PyTorch, prepare data pipelines in Python, and
        package models with Docker for our internal serving platform. We look for
        a degree in computer science or a related field, a solid grasp of machine
        learning basics, and projects that show you can take a model from a
        notebook to a working service. Mentoring and a structured first year are
        part of the programme.""",
        both(
            (2, "Fits: entry ML engineer role; has Python, PyTorch, ML, Docker"),
            ML_ROLE_FOR_BACKEND,
        ),
        skills=["Python", "PyTorch", "Machine Learning", "Docker"],
    ),
    job(
        2,
        "Junior Data Scientist",
        "Kestrel Insurance",
        "Entry Level",
        """Our pricing team needs a junior data scientist to build claim frequency
        models and explain them to actuaries. Day to day you will query policy data
        with SQL, explore it in Pandas, and fit and validate models in
        scikit-learn. You will present findings in short written notes. Up to two
        years of experience, including internships, is fine.""",
        both(
            (2, "Fits: entry data scientist; has SQL, Pandas, scikit-learn"),
            (0, "Data science role; not a backend or platform target"),
        ),
        skills=["Python", "SQL", "Pandas", "scikit-learn"],
    ),
    job(
        3,
        "AI Engineer, LLM Applications",
        "Brightloop Software",
        "Entry Level",
        """We build assistants for customer service teams on top of large language
        models. As an AI engineer you will design retrieval-augmented generation
        pipelines, write prompt and evaluation code in Python, and expose features
        through FastAPI services. Experience with LangChain or a similar framework,
        and with vector search, is a strong plus. This role suits a graduate with
        zero to two years of experience and real projects.""",
        both(
            (2, "Fits: entry AI role; has Python, LangChain, retrieval project, FastAPI"),
            (1, "Backend services in an AI product (FastAPI); entry is one step below"),
        ),
    ),
    job(
        4,
        "Associate NLP Engineer",
        "Wordwise Labs",
        "Entry Level",
        """Help us build text classification and entity extraction models for legal
        documents. You will fine-tune transformer models with Hugging Face
        Transformers and PyTorch, clean and label training data, and measure model
        quality. A degree in computing and a natural language processing project
        are required.""",
        both(
            (2, "Fits: entry NLP role; has Transformers, PyTorch, NLP project"),
            ML_ROLE_FOR_BACKEND,
        ),
        skills=["Python", "Hugging Face Transformers", "PyTorch", "Natural Language Processing"],
    ),
    job(
        5,
        "Machine Learning Engineer",
        "Orchid Mobility",
        "Mid Level",
        """We need a machine learning engineer with at least three years of
        experience to own our demand forecasting and dispatch models in production.
        You will run training jobs on Kubernetes, build MLOps tooling for model
        monitoring, and work with backend engineers on low-latency serving. Strong
        PyTorch and production experience required.""",
        both(
            (1, "ML role, but mid level (3+ years); profile is entry"),
            ML_ROLE_FOR_BACKEND,
        ),
        skills=["Python", "PyTorch", "MLOps", "Kubernetes"],
    ),
    job(
        6,
        "Senior Machine Learning Engineer",
        "Orchid Mobility",
        "Senior",
        """Lead the design of our next forecasting platform. You bring seven or more
        years of building machine learning systems, have led a team of engineers,
        and can set technical direction for model training, evaluation, and
        serving at scale.""",
        both(
            (0, "Senior role, 7+ years; profile is entry level"),
            ML_ROLE_FOR_BACKEND,
        ),
        skills=["Python", "PyTorch", "Machine Learning", "Distributed Systems"],
    ),
    job(
        7,
        "Lead Data Scientist",
        "Harrowgate Bank",
        "Lead",
        """Head a group of eight data scientists in our credit risk division. You
        will set the modelling roadmap, review model governance documents, and
        report to the chief risk officer. Ten or more years of experience and a
        track record of leading teams are required.""",
        both(
            (0, "Lead role, 10+ years; profile is entry level"),
            (0, "Data science lead; not a backend target, and two levels off"),
        ),
    ),
    job(
        8,
        "Data Analyst",
        "Seastar Retail Group",
        "Entry Level",
        """Turn sales and inventory data into weekly reports for store managers. You
        will write SQL queries, build Tableau dashboards, and answer ad hoc
        questions from the merchandising team. Strong Excel skills and attention to
        detail are needed; Python is a bonus.""",
        both(
            (1, "Data analyst: next to the data scientist target; has SQL"),
            (0, "Analytics role; not a backend target"),
        ),
        skills=["SQL", "Tableau", "Excel"],
        optional_skills=["Python"],
    ),
    job(
        9,
        "Junior Data Engineer",
        "Pinewave Media",
        "Entry Level",
        """Build and maintain the batch pipelines that feed our recommendation
        models. You will write Spark jobs in Python, schedule them with Airflow,
        and model tables in SQL. This is a junior role for someone with up to two
        years of experience who enjoys data quality work.""",
        both(
            (1, "Data engineer: next to the ML target; has Python and SQL, not Spark"),
            (1, "Data engineering is next to backend; entry level is one step below"),
        ),
        skills=["Python", "Spark", "Airflow", "SQL"],
    ),
    job(
        10,
        "Graduate MLOps Engineer",
        "Lumen Analytics",
        "Entry Level",
        """Our platform team is hiring a graduate to automate model training and
        deployment. You will write Python tooling, maintain CI/CD pipelines, build
        Docker images, and run workloads on Kubernetes. Interest in machine
        learning systems is expected; deep modelling skills are not.""",
        both(
            (1, "MLOps: next to the ML target; has Python, Docker, not Kubernetes or CI/CD"),
            (1, "Platform work next to the targets; entry level is one step below"),
        ),
        skills=["Python", "Docker", "Kubernetes", "CI/CD"],
    ),
    job(
        11,
        "Computer Vision Engineer",
        "Visiontrack Robotics",
        "Mid Level",
        """Develop real-time perception for warehouse robots. You will write C++ and
        CUDA code for detection models, optimise inference with OpenCV and
        TensorRT, and test on embedded hardware. Two or more years of computer
        vision experience required.""",
        both(
            (1, "Computer vision is an ML role, but mid level and C++ heavy"),
            ML_ROLE_FOR_BACKEND,
        ),
        skills=["C++", "CUDA", "OpenCV", "Computer Vision"],
    ),
    job(
        12,
        "Research Engineer, Machine Learning",
        "Northgate Institute for AI",
        "Mid Level",
        """Work with research scientists to turn new learning methods into
        reproducible experiments. You will implement papers in PyTorch, run
        large-scale training, and co-author publications. A master's or PhD with
        two to four years of research experience is preferred.""",
        both(
            (1, "ML research role; asks 2-4 years and a graduate degree"),
            ML_ROLE_FOR_BACKEND,
        ),
        skills=["Python", "PyTorch", "Machine Learning Research"],
    ),
    job(
        13,
        "AI Intern",
        "Brightloop Software",
        "Internship",
        """A six-month internship on our assistants team. You will help build
        evaluation sets for language model features, write Python scripts, and
        join daily stand-ups. Open to students in their final year.""",
        both(
            (1, "AI role, but an internship (one step below a graduate)"),
            (0, "Internship; two levels below a mid-level profile"),
        ),
        skills=["Python"],
    ),
    job(
        14,
        "Data Science Graduate Programme",
        "Harrowgate Bank",
        "Entry Level",
        """A two-year rotation programme for new graduates across fraud, marketing,
        and credit analytics. Each rotation builds models in Python and SQL with a
        senior data scientist as your mentor. We look for strong statistics,
        machine learning coursework, and at least one end-to-end project.""",
        both(
            (2, "Fits: graduate data science programme; has Python, SQL, ML projects"),
            (0, "Graduate data science programme; not a backend target"),
        ),
        skills=["Python", "SQL", "Machine Learning", "Statistics"],
    ),
    job(
        15,
        "Business Intelligence Analyst",
        "Coralpoint Hotels",
        "Entry Level",
        """Build Power BI dashboards for revenue and occupancy, maintain the data
        model behind them, and train hotel managers to use the reports. You will
        work mostly in Power BI, DAX, and Excel, with some SQL.""",
        both(
            (1, "BI analytics is next to data science; has some SQL, not Power BI"),
            (0, "BI reporting role; not a backend target"),
        ),
        skills=["Power BI", "DAX", "Excel"],
        optional_skills=["SQL"],
    ),
    job(
        16,
        "Quantitative Researcher",
        "Meridian Capital",
        "Mid Level",
        """Research and test systematic trading signals. You will write C++ and
        Python, apply time-series statistics, and work closely with traders. A PhD
        in a quantitative field and two or more years in trading are required.""",
        both(
            (0, "Quant trading research; not an ML engineering or data science target"),
            (0, "Quant research; not a backend target"),
        ),
        skills=["C++", "Python", "Time Series", "Statistics"],
    ),
    job(
        17,
        "Applied Scientist, Recommendations",
        "Pinewave Media",
        "Mid Level",
        """Improve the ranking models behind our video feed. You will design
        experiments, build features, and train deep learning recommenders in
        PyTorch. We expect three to five years of applied machine learning
        experience and strong statistics.""",
        both(
            (1, "Applied ML role; asks 3-5 years (one step above entry)"),
            ML_ROLE_FOR_BACKEND,
        ),
        skills=["Python", "PyTorch", "Recommender Systems", "Statistics"],
    ),
    job(
        18,
        "Junior AI Solutions Engineer",
        "Corvid Cloud",
        "Entry Level",
        """Help customers build their first generative AI features. You will build
        demos in Python that call large language model APIs, write small
        retrieval prototypes, and explain them to client teams. Clear speaking
        and a portfolio of AI projects matter more than years of experience.""",
        both(
            (2, "Fits: entry AI role; has Python and an LLM retrieval project"),
            (0, "Customer-facing AI role; not a backend target"),
        ),
    ),
    job(
        19,
        "Data Annotation Specialist",
        "Northgate Institute for AI",
        "Entry Level",
        """Label images and short texts that train our AI models. You will follow
        detailed guidelines, maintain labeling quality above our target, and flag
        unclear cases. No programming is needed; care and consistency are.""",
        both(
            (0, "Manual labeling work; not an ML engineering or data science role"),
            (0, "Labeling work; not a backend target"),
        ),
    ),
    job(
        20,
        "Email Marketing Executive",
        "Seastar Retail Group",
        "Entry Level",
        """Plan and send our weekly email campaigns to retail customers. You will
        maintain the mailing lists, write detailed campaign briefs, test subject
        lines, and report open and click rates. Experience with an email platform
        and an eye for detail are required.""",
        both(
            (0, "Marketing role; not a data or ML target"),
            (0, "Marketing role; not a backend target"),
        ),
        skills=["Email Marketing", "Copywriting"],
    ),
    job(
        21,
        "Digital Marketing Specialist",
        "Coralpoint Hotels",
        "Entry Level",
        """Run our digital advertising across search and social channels. You will
        manage budgets, plan campaigns, build audience segments, and report on
        bookings from each channel.""",
        both(
            (0, "Marketing role; not a data or ML target"),
            (0, "Marketing role; not a backend target"),
        ),
    ),
    job(
        22,
        "Training Coordinator",
        "Harbourline Logistics",
        "Entry Level",
        """Organise training for our warehouse and driver teams. You will maintain
        the training calendar, book rooms and trainers, keep attendance records,
        and collect feedback after each course.""",
        both(
            (0, "Training administration; not a data or ML target"),
            (0, "Training administration; not a backend target"),
        ),
    ),
    job(
        23,
        "Retail Store Supervisor",
        "Seastar Retail Group",
        "Entry Level",
        """Supervise a team of six in our flagship store. You will open and close
        the store, maintain stock displays, coach staff to give good service, and
        keep things going smoothly on busy weekends.""",
        both(
            (0, "Retail role; not a data or ML target"),
            (0, "Retail role; not a backend target"),
        ),
    ),
    job(
        24,
        "Machine Learning Platform Engineer",
        "Lumen Analytics",
        "Mid Level",
        """Build the platform that trains and serves our models. You will write Go
        services for the feature store, run training jobs on Kubernetes in AWS,
        and design gRPC interfaces that data scientists call. Three or more years
        of backend or platform engineering experience required; machine learning
        knowledge is a plus.""",
        both(
            (1, "ML platform: next to the ML target, but mid level with Go and Kubernetes"),
            (2, "Fits: mid platform engineer; has Go, Kubernetes, AWS, gRPC"),
        ),
        skills=["Go", "Kubernetes", "AWS", "gRPC"],
        optional_skills=["Machine Learning"],
    ),
    job(
        25,
        "Data Scientist, Experimentation",
        "Brightloop Software",
        "Mid Level",
        """Own A/B testing for our product teams. You will design experiments,
        analyse results in Python and SQL, and coach product managers on
        statistics. Two to four years of data science experience are required.""",
        both(
            (1, "Data scientist role; asks 2-4 years (one step above entry)"),
            (0, "Data science role; not a backend target"),
        ),
        skills=["Python", "SQL", "Statistics", "Experimentation"],
    ),
    job(
        26,
        "Graduate Software Engineer, Python",
        "Pinewave Media",
        "Entry Level",
        """Join a product team that builds data tools for editors. You will write
        Python services, small APIs, and tests, and work with data scientists on
        the features they need. Any computing graduate with Python projects is
        welcome.""",
        both(
            (1, "Graduate Python software role; next to the ML target"),
            (1, "Software role near backend; entry level is one step below"),
        ),
        skills=["Python"],
        optional_skills=["FastAPI", "SQL"],
    ),
    job(
        27,
        "NLP Data Scientist",
        "Wordwise Labs",
        "Entry Level",
        """Build models that sort customer messages in English and Chinese. You
        will clean text data, fine-tune transformer models, and measure accuracy
        for each language. Zero to two years of experience, Python, and a natural
        language processing project are required.""",
        both(
            (2, "Fits: entry NLP data scientist; has Python, Transformers, NLP project"),
            ML_ROLE_FOR_BACKEND,
        ),
    ),
    job(
        28,
        "Senior Data Engineer",
        "Meridian Capital",
        "Senior",
        """Design our streaming data platform. You will build Kafka and Spark
        pipelines, set data modelling standards, and mentor junior engineers. Six
        or more years of data engineering are required.""",
        both(
            (0, "Senior data engineer, 6+ years; profile is entry level"),
            (1, "Data engineering next to backend; has Kafka; senior is one step above"),
        ),
        skills=["Kafka", "Spark", "Scala", "Data Modelling"],
    ),
    job(
        29,
        "Statistician",
        "Fictional Statistics Board",
        "Mid Level",
        """Design household surveys and produce official estimates. You will work
        in R and SAS, write methodology notes, and check the quality of each
        release. Two or more years in survey statistics are required.""",
        both(
            (0, "Survey statistics; not an ML engineering or data science target"),
            (0, "Statistics role; not a backend target"),
        ),
        skills=["R", "SAS", "Survey Methodology"],
    ),
    job(
        30,
        "Junior ML Engineer, Edge Devices",
        "Visiontrack Robotics",
        "Entry Level",
        """Make our models run on small devices. You will quantise PyTorch models,
        convert them to TensorFlow Lite, and write C++ code to call them on
        embedded boards. A graduate with machine learning projects and some C++ is
        ideal.""",
        both(
            (1, "Entry ML role, but asks C++ and TensorFlow Lite (has PyTorch only)"),
            ML_ROLE_FOR_BACKEND,
        ),
        skills=["PyTorch", "TensorFlow Lite", "C++"],
        optional_skills=["Python"],
    ),
    job(
        31,
        "AI Product Manager",
        "Corvid Cloud",
        "Mid Level",
        """Own the roadmap for our AI assistant products. You will talk to
        customers, write requirements, and prioritise work for three engineering
        teams. Three or more years of product management are required.""",
        both(
            (0, "Product management role; not an engineering or data science target"),
            (0, "Product management role; not a backend target"),
        ),
    ),
    job(
        32,
        "Junior Data Scientist, Healthcare",
        "Fictional General Hospital",
        "Entry Level",
        """Build models that predict hospital readmission and explain them to
        clinicians. You will use Python, Pandas, scikit-learn, and SQL on
        anonymised patient records. A degree and machine learning projects are
        required; healthcare knowledge is a plus.""",
        both(
            (2, "Fits: entry data scientist; has Python, Pandas, scikit-learn, SQL"),
            (0, "Data science role; not a backend target"),
        ),
        skills=["Python", "Pandas", "scikit-learn", "SQL"],
    ),
    job(
        33,
        "Deep Learning Engineer",
        "Northgate Institute for AI",
        "Mid Level",
        """Scale training of large vision and language models. You will write
        distributed PyTorch code, profile GPU jobs, and improve training speed. Two
        or more years of deep learning engineering are required.""",
        both(
            (1, "Deep learning role; mid level (2+ years), one step above entry"),
            ML_ROLE_FOR_BACKEND,
        ),
        skills=["PyTorch", "Distributed Training", "CUDA"],
    ),
    job(
        34,
        "Analytics Engineer",
        "Kestrel Insurance",
        "Entry Level",
        """Model our warehouse tables in dbt and SQL so that analysts get clean,
        tested data. You will write transformations, document models, and add data
        tests. Up to two years of experience.""",
        both(
            (1, "Analytics engineering is next to data science; has SQL, not dbt"),
            (0, "Analytics role; not a backend target"),
        ),
        skills=["SQL", "dbt"],
    ),
    job(
        35,
        "LLM Evaluation Analyst",
        "Wordwise Labs",
        "Entry Level",
        """Check the quality of our language model outputs. You will write test
        prompts, score answers against guidelines, and script simple checks in
        Python. A background in linguistics or computing suits this role.""",
        both(
            (1, "AI evaluation role next to the ML target; little modelling"),
            (0, "Evaluation role; not a backend target"),
        ),
        optional_skills=["Python"],
    ),
]
