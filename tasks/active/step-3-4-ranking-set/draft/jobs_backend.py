"""Constructed backend, platform, and other jobs of the Step 3.4 ranking set.

Each job has a draft label for each profile: (label, reason). The labels
follow README.md and were written before any ranker ran on the set.
"""

from typing import Any, Dict, List

from jobs_ml import Label, both, job

BACKEND_FOR_ML: Label = (0, "Backend role; not an ML or data target, and not in Python")

JOBS_BACKEND: List[Dict[str, Any]] = [
    job(
        36,
        "Backend Engineer",
        "Crestline Payments",
        "Mid Level",
        """Build the services behind our card issuing product. You will design REST
        APIs in Java with Spring Boot, model data in PostgreSQL, and own your
        services in production. Three to five years of backend experience
        required.""",
        both(BACKEND_FOR_ML, (2, "Fits: mid backend; has Java, Spring Boot, PostgreSQL")),
        skills=["Java", "Spring Boot", "PostgreSQL", "REST APIs"],
    ),
    job(
        37,
        "Platform Engineer",
        "Tidepool Cloud",
        "Mid Level",
        """Run the Kubernetes platform that all our product teams deploy to. You
        will write Go operators, manage AWS infrastructure, and improve the
        developer experience of our deploy tooling. Two to five years of platform
        or infrastructure experience.""",
        both(
            (0, "Platform role; not an ML or data target"),
            (2, "Fits: mid platform engineer; has Go, Kubernetes, AWS"),
        ),
        skills=["Go", "Kubernetes", "AWS", "Docker"],
    ),
    job(
        38,
        "Software Engineer II, Payments",
        "Crestline Payments",
        "Mid Level",
        """Join the payments core team. You will build Java services that process
        transfers, publish and consume Kafka events, and keep our ledger correct
        under load. We look for three or more years of building backend systems.""",
        both(BACKEND_FOR_ML, (2, "Fits: mid backend; has Java, Kafka, PostgreSQL")),
        skills=["Java", "Kafka", "PostgreSQL", "Microservices"],
    ),
    job(
        39,
        "Backend Engineer, Go",
        "Fleetbridge",
        "Mid Level",
        """Write the Go services that track our vehicle fleet in real time. You will
        build gRPC APIs, cache hot data in Redis, and store history in PostgreSQL.
        Two or more years of Go in production required.""",
        both(BACKEND_FOR_ML, (2, "Fits: mid backend; has Go, gRPC, Redis, PostgreSQL")),
        skills=["Go", "gRPC", "Redis", "PostgreSQL"],
    ),
    job(
        40,
        "Senior Backend Engineer",
        "Crestline Payments",
        "Senior",
        """Lead the design of new payment products. You bring six or more years of
        Java backend experience, mentor engineers, and own system design reviews
        for your area.""",
        both(
            (0, "Senior backend role; not an ML target, and two levels off"),
            (1, "Backend target, but senior (6+ years); one step above mid"),
        ),
        skills=["Java", "Spring Boot", "System Design"],
    ),
    job(
        41,
        "Staff Engineer, Platform",
        "Tidepool Cloud",
        "Lead",
        """Set the technical direction for our infrastructure. Ten or more years of
        experience, deep Kubernetes and networking knowledge, and a record of
        leading large migrations are required.""",
        both(
            (0, "Staff platform role, 10+ years; not an ML target"),
            (0, "Staff level (10+ years); two levels above mid"),
        ),
        skills=["Kubernetes", "Networking", "Technical Leadership"],
    ),
    job(
        42,
        "Junior Backend Developer",
        "Fleetbridge",
        "Entry Level",
        """Start your career on our Java team. You will fix bugs, write tests, and
        build small features in our Spring Boot services. Zero to two years of
        experience.""",
        both(
            (0, "Java backend role; not an ML or data target"),
            (1, "Backend target, but junior (entry); one step below mid"),
        ),
        skills=["Java", "Spring Boot"],
    ),
    job(
        43,
        "Backend Engineer, Python",
        "Pinewave Media",
        "Mid Level",
        """Build the APIs behind our content management system. You will write
        Python services in Django, model data in PostgreSQL, and work with the
        frontend team. Three or more years of Django experience required.""",
        both(
            (1, "Python software role next to the ML target; mid level, one step above"),
            (1, "Backend target, but in Python and Django (has PostgreSQL only)"),
        ),
        skills=["Python", "Django", "PostgreSQL"],
    ),
    job(
        44,
        "Frontend Engineer",
        "Brightloop Software",
        "Mid Level",
        """Build the web app that our customers use every day. You will write
        JavaScript and TypeScript with React, build accessible components, and
        work closely with designers. Three or more years of frontend experience
        required.""",
        both(
            (0, "Frontend role; not an ML or data target"),
            (0, "Frontend JavaScript role; not a backend target (Java is not JavaScript)"),
        ),
        skills=["JavaScript", "TypeScript", "React", "CSS"],
    ),
    job(
        45,
        "Full-stack JavaScript Developer",
        "Seastar Retail Group",
        "Mid Level",
        """Build our online store end to end. You will write React on the front and
        Node.js with Express on the back, and connect both to MongoDB. Two or more
        years of full-stack JavaScript experience.""",
        both(
            (0, "Full-stack JavaScript role; not an ML or data target"),
            (1, "Full-stack is next to backend; skills are JavaScript, not Java"),
        ),
        skills=["JavaScript", "React", "Node.js", "MongoDB"],
    ),
    job(
        46,
        "Site Reliability Engineer",
        "Tidepool Cloud",
        "Mid Level",
        """Keep our services fast and available. You will run Kubernetes clusters,
        build Prometheus alerts, write Go tools for incident response, and lead
        post-incident reviews. Two or more years of SRE or operations
        experience.""",
        both(
            (0, "Site reliability role; not an ML or data target"),
            (1, "SRE is next to backend; has Kubernetes and Go"),
        ),
        skills=["Kubernetes", "Prometheus", "Go", "Linux"],
    ),
    job(
        47,
        "DevOps Engineer",
        "Harbourline Logistics",
        "Mid Level",
        """Automate our build and release process. You will write Terraform for
        AWS, maintain CI/CD pipelines, and support teams with Docker. Two to four
        years of DevOps experience.""",
        both(
            (0, "DevOps role; not an ML or data target"),
            (1, "DevOps is next to backend; has AWS and Docker, not Terraform"),
        ),
        skills=["Terraform", "AWS", "CI/CD", "Docker"],
    ),
    job(
        48,
        "Data Engineer",
        "Meridian Capital",
        "Mid Level",
        """Build the pipelines that move market data into our research platform.
        You will write Kafka consumers in Java, run Spark jobs, and model tables
        for analysts. Two to five years of data engineering.""",
        both(
            (1, "Data engineer next to the ML target; mid level, one step above"),
            (1, "Data engineering next to backend; has Java and Kafka"),
        ),
        skills=["Java", "Kafka", "Spark", "SQL"],
    ),
    job(
        49,
        "Full-stack Engineer",
        "Kestrel Insurance",
        "Mid Level",
        """Build the tools that our claims staff use. You will write Java services
        with Spring Boot and React screens, and own features from database to
        browser. Three or more years of experience.""",
        both(
            (0, "Full-stack Java role; not an ML or data target"),
            (1, "Full-stack is next to backend; has Java and Spring Boot"),
        ),
        skills=["Java", "Spring Boot", "React"],
    ),
    job(
        50,
        "iOS Developer",
        "Orchid Mobility",
        "Mid Level",
        """Build our rider app for iPhone. You will write Swift and SwiftUI, work
        with our API team, and ship weekly releases. Three or more years of iOS
        development.""",
        both(
            (0, "Mobile role; not an ML or data target"),
            (0, "Mobile role; not a backend target"),
        ),
        skills=["Swift", "SwiftUI", "iOS"],
    ),
    job(
        51,
        "Customer Support Specialist",
        "Corvid Cloud",
        "Entry Level",
        """Help our customers by chat and email. You need good written English, a
        calm manner, and a habit of going the extra mile. Experience with Google
        Workspace and a ticketing tool is a plus.""",
        both(
            (0, "Support role; not a data or ML target"),
            (0, "Support role; not a backend target"),
        ),
    ),
    job(
        52,
        "Sales Development Representative",
        "Tidepool Cloud",
        "Entry Level",
        """Open new conversations with companies that could use our platform. You
        are goal-oriented, good on the phone, and keep your pipeline up to date.
        Weekly targets and a clear bonus plan.""",
        both(
            (0, "Sales role; not a data or ML target"),
            (0, "Sales role; not a backend target"),
        ),
    ),
    job(
        53,
        "Backend Engineering Intern",
        "Crestline Payments",
        "Internship",
        """A three-month internship on our Java services. You will write tests,
        fix small bugs, and present a project at the end. Open to students.""",
        both(
            (0, "Java backend internship; not an ML or data target"),
            (0, "Internship; two levels below a mid-level profile"),
        ),
        skills=["Java"],
    ),
    job(
        54,
        "Principal Software Architect",
        "Harrowgate Bank",
        "Principal",
        """Shape the architecture of our core banking platform. Fifteen or more
        years of experience, enterprise architecture certification, and a record
        of leading bank-wide programmes are required.""",
        both(
            (0, "Principal architect, 15+ years; not an ML target"),
            (0, "Principal level; three levels above mid"),
        ),
        skills=["Enterprise Architecture", "Java", "System Design"],
    ),
    job(
        55,
        "Backend Engineer, Kotlin",
        "Fleetbridge",
        "Mid Level",
        """Build the booking services of our logistics marketplace. You will write
        Kotlin with Spring Boot, store data in PostgreSQL, and publish Kafka
        events. Java developers who want to move to Kotlin are welcome.""",
        both(
            BACKEND_FOR_ML,
            (2, "Fits: mid backend; has Spring Boot, PostgreSQL, Kafka; Java to Kotlin welcome"),
        ),
        skills=["Kotlin", "Spring Boot", "PostgreSQL", "Kafka"],
    ),
    job(
        56,
        "Golang Developer",
        "Pinewave Media",
        "Mid Level",
        """Write the Go microservices that power our streaming apps. You will build
        REST and gRPC APIs, work with MongoDB and Redis, and run services on
        Kubernetes. Two or more years of Go.""",
        both(BACKEND_FOR_ML, (2, "Fits: mid backend; has Go, gRPC, Redis, Kubernetes")),
        skills=["Go", "gRPC", "MongoDB", "Redis"],
    ),
    job(
        57,
        "Cloud Engineer",
        "Coralpoint Hotels",
        "Mid Level",
        """Run our move to AWS. You will set up networking, accounts, and security
        controls, and help teams deploy their apps. Two or more years of AWS and
        Linux administration.""",
        both(
            (0, "Cloud operations role; not an ML or data target"),
            (1, "Cloud engineering is next to platform; has AWS"),
        ),
        skills=["AWS", "Networking", "Linux"],
    ),
    job(
        58,
        "QA Automation Engineer",
        "Kestrel Insurance",
        "Mid Level",
        """Build automated tests for our web and API products. You will write
        Selenium and REST tests in Java, run them in CI, and report on test
        coverage. Two or more years of test automation.""",
        both(
            (0, "Test automation role; not an ML or data target"),
            (0, "Test automation role; not a backend target or next to one"),
        ),
        skills=["Selenium", "Java", "Test Automation"],
    ),
    job(
        59,
        "Integration Engineer",
        "Harbourline Logistics",
        "Mid Level",
        """Connect our warehouse system to partner carriers. You will build REST
        integrations in Java, map data formats, and monitor message flows. Two or
        more years of integration or backend work.""",
        both(
            (0, "Integration role; not an ML or data target"),
            (1, "Integration work is next to backend; has Java and REST APIs"),
        ),
        skills=["Java", "REST APIs", "Message Queues"],
    ),
    job(
        60,
        "Software Engineer, Search Backend",
        "Seastar Retail Group",
        "Mid Level",
        """Make product search fast and relevant. You will build Java services
        around Elasticsearch, tune queries, and add caching with Redis. Three or
        more years of backend experience.""",
        both(
            (0, "Search backend role in Java; not an ML or data target"),
            (2, "Fits: mid backend; has Java and Redis"),
        ),
        skills=["Java", "Elasticsearch", "Redis"],
    ),
    job(
        61,
        "Backend Engineer, .NET",
        "Harrowgate Bank",
        "Mid Level",
        """Build internal banking services in C# and .NET, with SQL Server and REST
        APIs. Three or more years of .NET backend experience.""",
        both(
            (0, ".NET backend role; not an ML or data target"),
            (1, "Backend target, but in C# and .NET"),
        ),
        skills=["C#", ".NET", "SQL Server"],
    ),
    job(
        62,
        "Graduate Software Engineer",
        "Fictional Government Technology Office",
        "Entry Level",
        """Our graduate programme takes engineers in any language. You will rotate
        through two product teams, mostly writing Java services, and learn our
        engineering practices. A computing degree and coding projects are
        needed.""",
        both(
            (1, "Graduate software role open to any language; next to the ML target"),
            (1, "Software role near backend; entry level is one step below"),
        ),
        optional_skills=["Java"],
    ),
    job(
        63,
        "Senior Platform Engineer",
        "Tidepool Cloud",
        "Senior",
        """Lead our Kubernetes platform roadmap. Seven or more years of platform
        experience, deep Go skills, and experience running multi-region clusters
        are required.""",
        both(
            (0, "Senior platform role; not an ML target, and two levels off"),
            (1, "Platform target, but senior (7+ years); one step above mid"),
        ),
        skills=["Kubernetes", "Go", "Multi-region Operations"],
    ),
    job(
        64,
        "Lead Backend Engineer",
        "Crestline Payments",
        "Lead",
        """Lead a team of six backend engineers. Eight or more years of Java
        experience and two or more years of people management are required.""",
        both(
            (0, "Lead role; not an ML target"),
            (0, "Lead level (8+ years, management); two levels above mid"),
        ),
        skills=["Java", "People Management"],
    ),
    job(
        65,
        "Database Administrator",
        "Harrowgate Bank",
        "Mid Level",
        """Look after our PostgreSQL and Oracle databases. You will plan backups,
        tune performance, and manage upgrades. Three or more years of DBA work.""",
        both(
            (0, "Database administration; not an ML or data science target"),
            (0, "Database administration; not a backend target or next to one"),
        ),
        skills=["PostgreSQL", "Oracle", "Database Administration"],
    ),
    job(
        66,
        "Backend Engineer, Remote",
        "Corvid Cloud",
        "Mid Level",
        """A fully remote role on our API team. You will build Java services on AWS,
        design REST APIs, and write clear technical documents. Three or more years
        of backend experience; any time zone within four hours of Singapore.""",
        both(BACKEND_FOR_ML, (2, "Fits: mid backend, remote; has Java, AWS, REST APIs")),
        skills=["Java", "AWS", "REST APIs"],
        location="Remote",
        work_mode="Remote",
    ),
    job(
        67,
        "Embedded Software Engineer",
        "Visiontrack Robotics",
        "Mid Level",
        """Write firmware for our robot controllers in C on an RTOS. You will
        debug hardware, write drivers, and test on the bench. Two or more years of
        embedded development.""",
        both(
            (0, "Embedded role; not an ML or data target"),
            (0, "Embedded role; not a backend target"),
        ),
        skills=["C", "RTOS", "Embedded Systems"],
    ),
    job(
        68,
        "API Engineer",
        "Fleetbridge",
        "Mid Level",
        """Own our public API. You will write Go services, keep the OpenAPI
        specification current, and store data in PostgreSQL. Two or more years of
        backend experience.""",
        both(BACKEND_FOR_ML, (2, "Fits: mid backend; has Go and PostgreSQL")),
        skills=["Go", "OpenAPI", "PostgreSQL"],
    ),
    job(
        69,
        "Technical Support Engineer",
        "Corvid Cloud",
        "Entry Level",
        """Solve technical problems for our enterprise customers. You will read
        logs on Linux servers, run SQL queries, and write clear answers in our
        ticketing system.""",
        both(
            (0, "Technical support role; not a data or ML target"),
            (0, "Support role; not a backend target"),
        ),
        skills=["Linux", "SQL"],
    ),
    job(
        70,
        "Event Streaming Engineer",
        "Meridian Capital",
        "Mid Level",
        """Build the event streaming backbone of our trading systems. You will write
        Java services with Kafka and Flink, design event schemas, and tune
        throughput. Three or more years of backend or streaming experience.""",
        both(BACKEND_FOR_ML, (2, "Fits: mid backend; has Java and Kafka")),
        skills=["Java", "Kafka", "Flink"],
    ),
]
