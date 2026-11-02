# Step 3.4 Ranking Set: Draft Labels to Check

Claude drafted every label with `draft/README.md` before any ranker ran. Check each row. To change a label, write the new label and a short reason in the last column (or tell Claude the job number and the label). Labels: 2 = apply, 1 = maybe, 0 = not relevant.

The job texts are in `draft/jobs_ml.py` (rk-001 to rk-035) and `draft/jobs_backend.py` (rk-036 to rk-070).

## Profile fresh_ml (Rina Tan): fresh graduate, targets ML engineer, data scientist, AI; entry level; Python, PyTorch, scikit-learn, Pandas, SQL, FastAPI, LangChain, Transformers, Docker

| Job | Title | Level | Company | Draft | Reason | Your label and reason |
|-----|-------|-------|---------|-------|--------|------------------------|
| rk-001 | Graduate Machine Learning Engineer | Entry | Lumen Analytics | 2 | Fits: entry ML engineer role; has Python, PyTorch, ML, Docker | |
| rk-002 | Junior Data Scientist | Entry | Kestrel Insurance | 2 | Fits: entry data scientist; has SQL, Pandas, scikit-learn | |
| rk-003 | AI Engineer, LLM Applications | Entry | Brightloop Software | 2 | Fits: entry AI role; has Python, LangChain, retrieval project, FastAPI | |
| rk-004 | Associate NLP Engineer | Entry | Wordwise Labs | 2 | Fits: entry NLP role; has Transformers, PyTorch, NLP project | |
| rk-005 | Machine Learning Engineer | Mid | Orchid Mobility | 1 | ML role, but mid level (3+ years); profile is entry | |
| rk-006 | Senior Machine Learning Engineer | Senior | Orchid Mobility | 0 | Senior role, 7+ years; profile is entry level | |
| rk-007 | Lead Data Scientist | Lead | Harrowgate Bank | 0 | Lead role, 10+ years; profile is entry level | |
| rk-008 | Data Analyst | Entry | Seastar Retail Group | 1 | Data analyst: next to the data scientist target; has SQL | |
| rk-009 | Junior Data Engineer | Entry | Pinewave Media | 1 | Data engineer: next to the ML target; has Python and SQL, not Spark | |
| rk-010 | Graduate MLOps Engineer | Entry | Lumen Analytics | 1 | MLOps: next to the ML target; has Python, Docker, not Kubernetes or CI/CD | |
| rk-011 | Computer Vision Engineer | Mid | Visiontrack Robotics | 1 | Computer vision is an ML role, but mid level and C++ heavy | |
| rk-012 | Research Engineer, Machine Learning | Mid | Northgate Institute for AI | 1 | ML research role; asks 2-4 years and a graduate degree | |
| rk-013 | AI Intern | Intern | Brightloop Software | 1 | AI role, but an internship (one step below a graduate) | |
| rk-014 | Data Science Graduate Programme | Entry | Harrowgate Bank | 2 | Fits: graduate data science programme; has Python, SQL, ML projects | |
| rk-015 | Business Intelligence Analyst | Entry | Coralpoint Hotels | 1 | BI analytics is next to data science; has some SQL, not Power BI | |
| rk-016 | Quantitative Researcher | Mid | Meridian Capital | 0 | Quant trading research; not an ML engineering or data science target | |
| rk-017 | Applied Scientist, Recommendations | Mid | Pinewave Media | 1 | Applied ML role; asks 3-5 years (one step above entry) | |
| rk-018 | Junior AI Solutions Engineer | Entry | Corvid Cloud | 2 | Fits: entry AI role; has Python and an LLM retrieval project | |
| rk-019 | Data Annotation Specialist | Entry | Northgate Institute for AI | 0 | Manual labeling work; not an ML engineering or data science role | |
| rk-020 | Email Marketing Executive | Entry | Seastar Retail Group | 0 | Marketing role; not a data or ML target | |
| rk-021 | Digital Marketing Specialist | Entry | Coralpoint Hotels | 0 | Marketing role; not a data or ML target | |
| rk-022 | Training Coordinator | Entry | Harbourline Logistics | 0 | Training administration; not a data or ML target | |
| rk-023 | Retail Store Supervisor | Entry | Seastar Retail Group | 0 | Retail role; not a data or ML target | |
| rk-024 | Machine Learning Platform Engineer | Mid | Lumen Analytics | 1 | ML platform: next to the ML target, but mid level with Go and Kubernetes | |
| rk-025 | Data Scientist, Experimentation | Mid | Brightloop Software | 1 | Data scientist role; asks 2-4 years (one step above entry) | |
| rk-026 | Graduate Software Engineer, Python | Entry | Pinewave Media | 1 | Graduate Python software role; next to the ML target | |
| rk-027 | NLP Data Scientist | Entry | Wordwise Labs | 2 | Fits: entry NLP data scientist; has Python, Transformers, NLP project | |
| rk-028 | Senior Data Engineer | Senior | Meridian Capital | 0 | Senior data engineer, 6+ years; profile is entry level | |
| rk-029 | Statistician | Mid | Fictional Statistics Board | 0 | Survey statistics; not an ML engineering or data science target | |
| rk-030 | Junior ML Engineer, Edge Devices | Entry | Visiontrack Robotics | 1 | Entry ML role, but asks C++ and TensorFlow Lite (has PyTorch only) | |
| rk-031 | AI Product Manager | Mid | Corvid Cloud | 0 | Product management role; not an engineering or data science target | |
| rk-032 | Junior Data Scientist, Healthcare | Entry | Fictional General Hospital | 2 | Fits: entry data scientist; has Python, Pandas, scikit-learn, SQL | |
| rk-033 | Deep Learning Engineer | Mid | Northgate Institute for AI | 1 | Deep learning role; mid level (2+ years), one step above entry | |
| rk-034 | Analytics Engineer | Entry | Kestrel Insurance | 1 | Analytics engineering is next to data science; has SQL, not dbt | |
| rk-035 | LLM Evaluation Analyst | Entry | Wordwise Labs | 1 | AI evaluation role next to the ML target; little modelling | |
| rk-036 | Backend Engineer | Mid | Crestline Payments | 0 | Backend role; not an ML or data target, and not in Python | |
| rk-037 | Platform Engineer | Mid | Tidepool Cloud | 0 | Platform role; not an ML or data target | |
| rk-038 | Software Engineer II, Payments | Mid | Crestline Payments | 0 | Backend role; not an ML or data target, and not in Python | |
| rk-039 | Backend Engineer, Go | Mid | Fleetbridge | 0 | Backend role; not an ML or data target, and not in Python | |
| rk-040 | Senior Backend Engineer | Senior | Crestline Payments | 0 | Senior backend role; not an ML target, and two levels off | |
| rk-041 | Staff Engineer, Platform | Lead | Tidepool Cloud | 0 | Staff platform role, 10+ years; not an ML target | |
| rk-042 | Junior Backend Developer | Entry | Fleetbridge | 0 | Java backend role; not an ML or data target | |
| rk-043 | Backend Engineer, Python | Mid | Pinewave Media | 1 | Python software role next to the ML target; mid level, one step above | |
| rk-044 | Frontend Engineer | Mid | Brightloop Software | 0 | Frontend role; not an ML or data target | |
| rk-045 | Full-stack JavaScript Developer | Mid | Seastar Retail Group | 0 | Full-stack JavaScript role; not an ML or data target | |
| rk-046 | Site Reliability Engineer | Mid | Tidepool Cloud | 0 | Site reliability role; not an ML or data target | |
| rk-047 | DevOps Engineer | Mid | Harbourline Logistics | 0 | DevOps role; not an ML or data target | |
| rk-048 | Data Engineer | Mid | Meridian Capital | 1 | Data engineer next to the ML target; mid level, one step above | |
| rk-049 | Full-stack Engineer | Mid | Kestrel Insurance | 0 | Full-stack Java role; not an ML or data target | |
| rk-050 | iOS Developer | Mid | Orchid Mobility | 0 | Mobile role; not an ML or data target | |
| rk-051 | Customer Support Specialist | Entry | Corvid Cloud | 0 | Support role; not a data or ML target | |
| rk-052 | Sales Development Representative | Entry | Tidepool Cloud | 0 | Sales role; not a data or ML target | |
| rk-053 | Backend Engineering Intern | Intern | Crestline Payments | 0 | Java backend internship; not an ML or data target | |
| rk-054 | Principal Software Architect | Principal | Harrowgate Bank | 0 | Principal architect, 15+ years; not an ML target | |
| rk-055 | Backend Engineer, Kotlin | Mid | Fleetbridge | 0 | Backend role; not an ML or data target, and not in Python | |
| rk-056 | Golang Developer | Mid | Pinewave Media | 0 | Backend role; not an ML or data target, and not in Python | |
| rk-057 | Cloud Engineer | Mid | Coralpoint Hotels | 0 | Cloud operations role; not an ML or data target | |
| rk-058 | QA Automation Engineer | Mid | Kestrel Insurance | 0 | Test automation role; not an ML or data target | |
| rk-059 | Integration Engineer | Mid | Harbourline Logistics | 0 | Integration role; not an ML or data target | |
| rk-060 | Software Engineer, Search Backend | Mid | Seastar Retail Group | 0 | Search backend role in Java; not an ML or data target | |
| rk-061 | Backend Engineer, .NET | Mid | Harrowgate Bank | 0 | .NET backend role; not an ML or data target | |
| rk-062 | Graduate Software Engineer | Entry | Fictional Government Technology Office | 1 | Graduate software role open to any language; next to the ML target | |
| rk-063 | Senior Platform Engineer | Senior | Tidepool Cloud | 0 | Senior platform role; not an ML target, and two levels off | |
| rk-064 | Lead Backend Engineer | Lead | Crestline Payments | 0 | Lead role; not an ML target | |
| rk-065 | Database Administrator | Mid | Harrowgate Bank | 0 | Database administration; not an ML or data science target | |
| rk-066 | Backend Engineer, Remote | Mid | Corvid Cloud | 0 | Backend role; not an ML or data target, and not in Python | |
| rk-067 | Embedded Software Engineer | Mid | Visiontrack Robotics | 0 | Embedded role; not an ML or data target | |
| rk-068 | API Engineer | Mid | Fleetbridge | 0 | Backend role; not an ML or data target, and not in Python | |
| rk-069 | Technical Support Engineer | Entry | Corvid Cloud | 0 | Technical support role; not a data or ML target | |
| rk-070 | Event Streaming Engineer | Mid | Meridian Capital | 0 | Backend role; not an ML or data target, and not in Python | |

## Profile mid_backend (Daniel Ong): 4.4 years, targets backend engineer, platform engineer, Java; mid level; Java, Spring Boot, Go, PostgreSQL, Redis, Kafka, Docker, Kubernetes, AWS, gRPC

| Job | Title | Level | Company | Draft | Reason | Your label and reason |
|-----|-------|-------|---------|-------|--------|------------------------|
| rk-001 | Graduate Machine Learning Engineer | Entry | Lumen Analytics | 0 | Machine learning role; not a backend or platform target | |
| rk-002 | Junior Data Scientist | Entry | Kestrel Insurance | 0 | Data science role; not a backend or platform target | |
| rk-003 | AI Engineer, LLM Applications | Entry | Brightloop Software | 0 | LLM application role; not a backend or platform target | |
| rk-004 | Associate NLP Engineer | Entry | Wordwise Labs | 0 | Machine learning role; not a backend or platform target | |
| rk-005 | Machine Learning Engineer | Mid | Orchid Mobility | 0 | Machine learning role; not a backend or platform target | |
| rk-006 | Senior Machine Learning Engineer | Senior | Orchid Mobility | 0 | Machine learning role; not a backend or platform target | |
| rk-007 | Lead Data Scientist | Lead | Harrowgate Bank | 0 | Data science lead; not a backend target, and two levels off | |
| rk-008 | Data Analyst | Entry | Seastar Retail Group | 0 | Analytics role; not a backend target | |
| rk-009 | Junior Data Engineer | Entry | Pinewave Media | 1 | Data engineering is next to backend; entry level is one step below | |
| rk-010 | Graduate MLOps Engineer | Entry | Lumen Analytics | 1 | Platform work next to the targets; entry level is one step below | |
| rk-011 | Computer Vision Engineer | Mid | Visiontrack Robotics | 0 | Machine learning role; not a backend or platform target | |
| rk-012 | Research Engineer, Machine Learning | Mid | Northgate Institute for AI | 0 | Machine learning role; not a backend or platform target | |
| rk-013 | AI Intern | Intern | Brightloop Software | 0 | Internship; two levels below a mid-level profile | |
| rk-014 | Data Science Graduate Programme | Entry | Harrowgate Bank | 0 | Graduate data science programme; not a backend target | |
| rk-015 | Business Intelligence Analyst | Entry | Coralpoint Hotels | 0 | BI reporting role; not a backend target | |
| rk-016 | Quantitative Researcher | Mid | Meridian Capital | 0 | Quant research; not a backend target | |
| rk-017 | Applied Scientist, Recommendations | Mid | Pinewave Media | 0 | Machine learning role; not a backend or platform target | |
| rk-018 | Junior AI Solutions Engineer | Entry | Corvid Cloud | 0 | Customer-facing AI role; not a backend target | |
| rk-019 | Data Annotation Specialist | Entry | Northgate Institute for AI | 0 | Labeling work; not a backend target | |
| rk-020 | Email Marketing Executive | Entry | Seastar Retail Group | 0 | Marketing role; not a backend target | |
| rk-021 | Digital Marketing Specialist | Entry | Coralpoint Hotels | 0 | Marketing role; not a backend target | |
| rk-022 | Training Coordinator | Entry | Harbourline Logistics | 0 | Training administration; not a backend target | |
| rk-023 | Retail Store Supervisor | Entry | Seastar Retail Group | 0 | Retail role; not a backend target | |
| rk-024 | Machine Learning Platform Engineer | Mid | Lumen Analytics | 2 | Fits: mid platform engineer; has Go, Kubernetes, AWS, gRPC | |
| rk-025 | Data Scientist, Experimentation | Mid | Brightloop Software | 0 | Data science role; not a backend target | |
| rk-026 | Graduate Software Engineer, Python | Entry | Pinewave Media | 1 | Software role near backend; entry level is one step below | |
| rk-027 | NLP Data Scientist | Entry | Wordwise Labs | 0 | Machine learning role; not a backend or platform target | |
| rk-028 | Senior Data Engineer | Senior | Meridian Capital | 1 | Data engineering next to backend; has Kafka; senior is one step above | |
| rk-029 | Statistician | Mid | Fictional Statistics Board | 0 | Statistics role; not a backend target | |
| rk-030 | Junior ML Engineer, Edge Devices | Entry | Visiontrack Robotics | 0 | Machine learning role; not a backend or platform target | |
| rk-031 | AI Product Manager | Mid | Corvid Cloud | 0 | Product management role; not a backend target | |
| rk-032 | Junior Data Scientist, Healthcare | Entry | Fictional General Hospital | 0 | Data science role; not a backend target | |
| rk-033 | Deep Learning Engineer | Mid | Northgate Institute for AI | 0 | Machine learning role; not a backend or platform target | |
| rk-034 | Analytics Engineer | Entry | Kestrel Insurance | 0 | Analytics role; not a backend target | |
| rk-035 | LLM Evaluation Analyst | Entry | Wordwise Labs | 0 | Evaluation role; not a backend target | |
| rk-036 | Backend Engineer | Mid | Crestline Payments | 2 | Fits: mid backend; has Java, Spring Boot, PostgreSQL | |
| rk-037 | Platform Engineer | Mid | Tidepool Cloud | 2 | Fits: mid platform engineer; has Go, Kubernetes, AWS | |
| rk-038 | Software Engineer II, Payments | Mid | Crestline Payments | 2 | Fits: mid backend; has Java, Kafka, PostgreSQL | |
| rk-039 | Backend Engineer, Go | Mid | Fleetbridge | 2 | Fits: mid backend; has Go, gRPC, Redis, PostgreSQL | |
| rk-040 | Senior Backend Engineer | Senior | Crestline Payments | 1 | Backend target, but senior (6+ years); one step above mid | |
| rk-041 | Staff Engineer, Platform | Lead | Tidepool Cloud | 0 | Staff level (10+ years); two levels above mid | |
| rk-042 | Junior Backend Developer | Entry | Fleetbridge | 1 | Backend target, but junior (entry); one step below mid | |
| rk-043 | Backend Engineer, Python | Mid | Pinewave Media | 1 | Backend target, but in Python and Django (has PostgreSQL only) | |
| rk-044 | Frontend Engineer | Mid | Brightloop Software | 0 | Frontend JavaScript role; not a backend target (Java is not JavaScript) | |
| rk-045 | Full-stack JavaScript Developer | Mid | Seastar Retail Group | 1 | Full-stack is next to backend; skills are JavaScript, not Java | |
| rk-046 | Site Reliability Engineer | Mid | Tidepool Cloud | 1 | SRE is next to backend; has Kubernetes and Go | |
| rk-047 | DevOps Engineer | Mid | Harbourline Logistics | 1 | DevOps is next to backend; has AWS and Docker, not Terraform | |
| rk-048 | Data Engineer | Mid | Meridian Capital | 1 | Data engineering next to backend; has Java and Kafka | |
| rk-049 | Full-stack Engineer | Mid | Kestrel Insurance | 1 | Full-stack is next to backend; has Java and Spring Boot | |
| rk-050 | iOS Developer | Mid | Orchid Mobility | 0 | Mobile role; not a backend target | |
| rk-051 | Customer Support Specialist | Entry | Corvid Cloud | 0 | Support role; not a backend target | |
| rk-052 | Sales Development Representative | Entry | Tidepool Cloud | 0 | Sales role; not a backend target | |
| rk-053 | Backend Engineering Intern | Intern | Crestline Payments | 0 | Internship; two levels below a mid-level profile | |
| rk-054 | Principal Software Architect | Principal | Harrowgate Bank | 0 | Principal level; three levels above mid | |
| rk-055 | Backend Engineer, Kotlin | Mid | Fleetbridge | 2 | Fits: mid backend; has Spring Boot, PostgreSQL, Kafka; Java to Kotlin welcome | |
| rk-056 | Golang Developer | Mid | Pinewave Media | 2 | Fits: mid backend; has Go, gRPC, Redis, Kubernetes | |
| rk-057 | Cloud Engineer | Mid | Coralpoint Hotels | 1 | Cloud engineering is next to platform; has AWS | |
| rk-058 | QA Automation Engineer | Mid | Kestrel Insurance | 0 | Test automation role; not a backend target or next to one | |
| rk-059 | Integration Engineer | Mid | Harbourline Logistics | 1 | Integration work is next to backend; has Java and REST APIs | |
| rk-060 | Software Engineer, Search Backend | Mid | Seastar Retail Group | 2 | Fits: mid backend; has Java and Redis | |
| rk-061 | Backend Engineer, .NET | Mid | Harrowgate Bank | 1 | Backend target, but in C# and .NET | |
| rk-062 | Graduate Software Engineer | Entry | Fictional Government Technology Office | 1 | Software role near backend; entry level is one step below | |
| rk-063 | Senior Platform Engineer | Senior | Tidepool Cloud | 1 | Platform target, but senior (7+ years); one step above mid | |
| rk-064 | Lead Backend Engineer | Lead | Crestline Payments | 0 | Lead level (8+ years, management); two levels above mid | |
| rk-065 | Database Administrator | Mid | Harrowgate Bank | 0 | Database administration; not a backend target or next to one | |
| rk-066 | Backend Engineer, Remote | Mid | Corvid Cloud | 2 | Fits: mid backend, remote; has Java, AWS, REST APIs | |
| rk-067 | Embedded Software Engineer | Mid | Visiontrack Robotics | 0 | Embedded role; not a backend target | |
| rk-068 | API Engineer | Mid | Fleetbridge | 2 | Fits: mid backend; has Go and PostgreSQL | |
| rk-069 | Technical Support Engineer | Entry | Corvid Cloud | 0 | Support role; not a backend target | |
| rk-070 | Event Streaming Engineer | Mid | Meridian Capital | 2 | Fits: mid backend; has Java and Kafka | |
