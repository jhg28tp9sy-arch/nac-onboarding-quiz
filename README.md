# NAC Connect

NAC Connect helps new National Ability Center employees learn coworkers’ names, job titles, and departments through an interactive org chart, a searchable staff directory, and three quizzes.

Before starting a quiz, select your staff profile from the org chart or enter your first and last name. Open **Quiz history** from Home to review your attempts and download results during the signed-in browser session. Each perfect full quiz or Mastery Exam earns a PDF certificate with the score and award time in UTC. Missed-question retries appear as separate practice attempts.

Open **Quiz options** during any question to pause, restart, or end your current attempt. Pausing keeps your submitted answers and your place. Ending early saves a partial result when you have submitted answers.

## Deploy to Streamlit Community Cloud

Deploy from the GitHub repository `jhg28tp9sy-arch/nac-onboarding-quiz`, branch `main`, and main file path `app.py`. The app password controls access to the running Streamlit app. The public GitHub repository contains the roster and portraits.

The default test password is `learnnac`. To override it, set the following value under **Settings → Secrets**.

```toml
NAC_ACCESS_PASSWORD = "replace-with-your-access-password"
```

### Private results log

Add the database connection under **Settings → Secrets** to enable the shared history on Streamlit Community Cloud.

```toml
NAC_RESULTS_DATABASE_URL = "postgresql://user:password@host/database?sslmode=require"
```

The default results log password is `moose25` and is visible in this public repository. Set `NAC_RESULTS_PASSWORD` in **Secrets** to override it.

Use a private PostgreSQL database with a role that can create and read or write `nac_quiz_results`. The app creates the table when it first connects. Open **Results log** from Home and unlock it with the separate log password to view or export the history. Results include the participant name, staff ID when selected from the org chart, quiz, attempt type, score, and UTC timestamp. History starts when the database is configured, and entries use self-reported identities.

## Run locally

Use Python 3.11 or 3.12. To override the test password locally, add the secret to `.streamlit/secrets.toml`.

```sh
pip install -r requirements.txt
streamlit run app.py
python -m unittest discover -s tests -v
```

The local roster manager is disabled by default.

To test the results log locally, set `NAC_RESULTS_SQLITE_PATH` to a local file ending in `.sqlite3`. This setting can go in `.streamlit/secrets.toml` or the environment. Use PostgreSQL for the hosted app so history survives redeploys.

The staff directory, org chart, and all three quizzes use the Paylocity roster in `data/staff.csv`. The org chart uses `data/reporting.json` to link staff IDs to their managers. Select a person’s row to expand their reporting branch in place. **Find staff** searches the roster and can jump from a result to that person’s chart entry.

Role Recall covers the full roster. Name Recall and scored Mastery Exam questions use staff with portraits. Mastery includes the other staff in the answer key under **Review-only profiles**.

## Branding

The [National Ability Center website](https://nationalabilitycenter.org/) supplies the header wordmark, icon, and palette.
