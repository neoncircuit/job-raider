# Fresh Graduate Profile Template

This template is designed to help you fill out your job-raider profile with the information that matters most for fresh graduate job matching.

## Why This Matters

With fresh grad mode enabled, your profile is scored as:
- **Projects (35%)** - Academic projects, portfolio, hackathons
- **Skills (30%)** - Technical skills match against job requirements
- **Education (20%)** - Degree level, major relevance, GPA
- **Experience (10%)** - Internships, part-time work (reduced weight)
- **Location (5%)** - Geographic preferences

## Step 1: Education (20% of your score)

### Required Fields:
```json
{
  "degree": "Bachelor of Science in Computer Science",
  "school": "University Name",
  "location": "City, State",
  "start_date": "2020-09-01",
  "end_date": "2024-05-01",
  "gpa": 3.5,
  "coursework": [
    "Data Structures and Algorithms",
    "Database Systems",
    "Web Development",
    "Machine Learning"
  ],
  "honors": [
    "Dean's List",
    "Computer Science Department Award"
  ]
}
```

### Tips:
- **GPA matters**: 3.5+ gets full points, 3.0+ gets partial credit
- **Relevant majors**: CS, Software Engineering, Data Science, Math, Physics score highest
- **Coursework**: List relevant classes that match your target jobs
- **Honors**: Dean's List, awards, competitions add bonus points

## Step 2: Projects (35% of your score) - **MOST IMPORTANT**

### Project Template:
```json
{
  "name": "Job Application Automation Tool",
  "description": "Built a tool to automate job applications using Python and Selenium",
  "long_description": "Full-stack application that scrapes job boards, matches resumes to job descriptions using NLP, and auto-submits applications. Reduced application time by 80%.",
  "technologies": [
    "Python",
    "FastAPI", 
    "React",
    "Selenium",
    "PostgreSQL",
    "Docker"
  ],
  "url": "https://github.com/yourusername/job-raider",
  "highlights": [
    "Scraped 50+ job boards daily",
    "NLP-based resume matching with 85% accuracy",
    "Auto-submitted 100+ applications with 20% response rate"
  ],
  "role": "Full Stack Developer",
  "start_date": "2023-09-01",
  "end_date": "2024-01-15"
}
```

### Project Types That Score High:
1. **Academic Capstone** - Senior design/final year project (20 points base)
2. **Personal Projects** - GitHub portfolio (15 points base)
3. **Hackathon** - Participation or awards (10 points base)
4. **Research** - Published research, papers (15 points base)

### Quality Boosters:
- **GitHub link with stars/forks** (+3 points)
- **Deployed application** (+3 points)
- **Technical blog posts** (+2 points)
- **Documentation** (+2 points)
- **Test coverage** (+2 points)

## Step 3: Skills (30% of your score)

### Skill Template:
```json
{
  "name": "Python",
  "category": "programming_language",
  "proficiency": "Advanced",
  "years_of_experience": 2,
  "last_used": "2024-05-01"
}
```

### Skill Categories:
- **Programming Languages**: Python, JavaScript, TypeScript, Java, C++, Go
- **Frameworks**: React, Next.js, FastAPI, Django, Flask
- **Tools**: Git, Docker, Kubernetes, AWS
- **Databases**: PostgreSQL, MongoDB, Redis
- **Domains**: Machine Learning, Web Development, DevOps

### Tips:
- **Be honest but strategic** - List skills you can actually demonstrate
- **Show, don't just tell** - Each skill should be backed by a project
- **Group by category** - Helps match against job requirements
- **Include proficiency level** - Beginner, Intermediate, Advanced, Expert

## Step 4: Experience (10% of your score)

For fresh grads, this includes:
- Internships
- Part-time work
- Research assistant positions
- Teaching assistant roles
- Freelance work

### Experience Template:
```json
{
  "title": "Software Engineering Intern",
  "company": "Tech Company",
  "location": "Remote",
  "start_date": "2023-06-01",
  "end_date": "2023-09-01",
  "current": false,
  "description": "Worked on backend API development using Python and FastAPI",
  "highlights": [
    "Developed RESTful APIs serving 10k+ requests daily",
    "Implemented caching reducing response time by 40%",
    "Collaborated with 3-person team using Git/GitHub"
  ],
  "technologies": ["Python", "FastAPI", "Redis", "Docker"]
}
```

## Step 5: Target Jobs (Improves Matching Quality)

```json
{
  "keywords": ["software engineer", "full stack", "backend developer"],
  "locations": ["Remote", "San Francisco", "New York"],
  "experience_levels": ["Entry Level", "Junior"],
  "remote_preference": true,
  "industries": ["Technology", "Finance", "Healthcare"],
  "company_sizes": ["1-50", "51-200", "201-1000"]
}
```

## Priority Action Items for Maximum Score

### Immediate (This Week):
1. ✅ **List 3-5 projects** with GitHub links
2. ✅ **Add education details** (degree, school, GPA, coursework)
3. ✅ **Identify 10-15 skills** you're confident in
4. ✅ **Define target job keywords** (software engineer, developer, etc.)

### Short-term (Next 2 Weeks):
1. ✅ **Improve GitHub profiles** - Add README.md, screenshots, documentation
2. ✅ **Deploy at least 2 projects** - Make them publicly accessible
3. ✅ **Write technical blog posts** - About your projects/learning journey
4. ✅ **Get recommendations** - LinkedIn endorsements from professors/colleagues

### Medium-term (Next Month):
1. ✅ **Contribute to open source** - Even small PRs help
2. ✅ **Build a portfolio website** - Showcase your best work
3. ✅ **Create project demos** - Screen recordings or live demos
4. ✅ **Network strategically** - Connect with professionals in your field

## Common Fresh Grad Mistakes to Avoid

❌ **Don't**:
- List too many skills without proof
- exaggerate proficiency levels
- include irrelevant coursework
- Leave projects undocumented

✅ **Do**:
- Focus on 3-5 strong projects
- Be honest about skill levels
- Highlight relevant coursework
- Document everything with GitHub/deployments

## Example: Complete Profile Entry

```json
{
  "name": "Your Name",
  "contact": {
    "email": "you@example.com",
    "phone": "+1-555-123-4567",
    "location": "San Francisco, CA",
    "github": "https://github.com/yourusername",
    "portfolio": "https://yourportfolio.com"
  },
  "summary": "Fresh graduate computer science student with passion for full-stack development and automation. Built job-raider, a comprehensive job application automation tool.",
  "skills": [
    {"name": "Python", "category": "programming_language", "proficiency": "Advanced"},
    {"name": "React", "category": "framework", "proficiency": "Intermediate"},
    {"name": "FastAPI", "category": "framework", "proficiency": "Intermediate"},
    {"name": "Docker", "category": "tool", "proficiency": "Intermediate"},
    {"name": "PostgreSQL", "category": "database", "proficiency": "Intermediate"}
  ],
  "education": [{
    "degree": "Bachelor of Science in Computer Science",
    "school": "University Name",
    "gpa": 3.6,
    "coursework": ["Data Structures", "Algorithms", "Database Systems", "Web Development"],
    "honors": ["Dean's List 2022-2024"]
  }],
  "projects": [
    {
      "name": "Job Raider",
      "description": "Comprehensive job application automation platform",
      "technologies": ["Python", "FastAPI", "React", "Docker", "PostgreSQL"],
      "url": "https://github.com/yourusername/job-raider",
      "highlights": [
        "Automated job scraping from 5+ sources",
        "Built fresh grad scoring algorithm",
        "Implemented DISC personality assessment",
        "Deployed with Docker Compose"
      ]
    },
    {
      "name": "Portfolio Website",
      "description": "Personal portfolio showcasing projects and skills",
      "technologies": ["React", "Next.js", "TailwindCSS"],
      "url": "https://yourportfolio.com",
      "highlights": [
        "Responsive design for mobile/desktop",
        "Optimized for SEO and accessibility",
        "Integrated contact form and analytics"
      ]
    },
    {
      "name": "E-commerce API",
      "description": "RESTful API for e-commerce platform",
      "technologies": ["Python", "Django", "PostgreSQL", "Redis"],
      "url": "https://github.com/yourusername/ecommerce-api",
      "highlights": [
        "Handled 10k+ daily requests",
        "Implemented caching for performance",
        "Built admin dashboard for product management"
      ]
    }
  ],
  "experience": [{
    "title": "Software Development Intern",
    "company": "Startup Inc",
    "start_date": "2023-06-01",
    "end_date": "2023-09-01",
    "description": "Full stack development for early-stage startup",
    "technologies": ["React", "Node.js", "MongoDB", "AWS"],
    "highlights": [
      "Built customer-facing features",
      "Reduced page load time by 50%",
      "Implemented A/B testing framework"
    ]
  }],
  "targets": {
    "keywords": ["software engineer", "full stack developer", "backend developer"],
    "locations": ["Remote", "San Francisco", "New York"],
    "experience_levels": ["Entry Level", "Junior"],
    "remote_preference": true
  }
}
```

## Next Steps

Once you have your profile data ready, you can:
1. Upload it through the job-raider UI
2. Test the fresh grad scoring with real job listings
3. See your match scores improve from 40-50 to 70-85

---

**Remember**: As a fresh grad, your projects and education are your strongest assets. Focus on making those shine!
