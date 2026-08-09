# IT PM Job Search Agent

Python + GitHub Actions job-search agent for senior IT Project / Program / Engineering Management roles.

## Current sources
- Arbeitnow — European job listings
- Remotive — remote job listings

## Matching
The agent prioritizes project/program/delivery/engineering-management roles, AI/ML and technical leadership, stakeholder management, Agile/Scrum and delivery. It penalizes explicit German/Czech fluency requirements and roles where hands-on production coding is a core requirement.

Geography is tuned for Prague onsite/hybrid roles and plausible Europe/EMEA remote opportunities. Remote eligibility still needs final verification because a remote vacancy may restrict the employee's country of residence.

## Run manually on GitHub
Open **Actions → IT PM Job Search → Run workflow**.

The workflow also runs daily at 05:15 UTC and stores results as an Actions artifact. It commits the latest results and seen-job history back to the repository.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python search_jobs.py
```

Results are written to `output/jobs.csv` and `output/jobs.md`.

## Configuration
Edit `config.json` to change target titles, positive/negative keywords, geography, minimum score, posting age and enabled sources.

## GitHub Actions permission
If the workflow can run but cannot commit its results, go to **Settings → Actions → General → Workflow permissions** and enable **Read and write permissions**.

## Next stage
Expand discovery with direct ATS/company adapters such as Greenhouse, Lever and SmartRecruiters, then add a second-stage classifier for Czechia remote eligibility, actual language requirements, hands-on coding expectations and candidate fit.
