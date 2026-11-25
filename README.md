# NAC Connect

NAC Connect helps new National Ability Center employees learn coworkers’ names, job titles, and departments through an interactive org chart, a searchable staff directory, and three quizzes.

Open **Quiz history** from Home to review completed attempts and download their results as CSV during the signed-in browser session. Each perfect full quiz or Mastery Exam earns a PDF certificate with the score and award time in UTC. Missed-question retries appear as separate practice attempts in the history.

Open **Quiz options** during any question to pause, restart, or end your current attempt. Pausing keeps your submitted answers and your place. Ending early saves a partial result when you have submitted answers.

## Deploy to Streamlit Community Cloud

Deploy from the GitHub repository `jhg28tp9sy-arch/nac-onboarding-quiz`, branch `main`, and main file path `app.py`. The app password controls access to the running Streamlit app. The public GitHub repository contains the roster and portraits.

The default test password is `learnnac`. To override it, set the following value under **Settings → Secrets**.

```toml
NAC_ACCESS_PASSWORD = "replace-with-your-access-password"
```

## Run locally

Use Python 3.11 or 3.12. To override the test password locally, add the secret to `.streamlit/secrets.toml`.

```sh
pip install -r requirements.txt
streamlit run app.py
python -m unittest discover -s tests -v
```

The local roster manager is disabled by default.

The staff directory, org chart, and all three quizzes use the Paylocity roster in `data/staff.csv`. The org chart uses `data/reporting.json` to link staff IDs to their managers. Select a person’s row to expand their reporting branch in place. **Find staff** searches the roster and can jump from a result to that person’s chart entry.

Role Recall covers the full roster. Name Recall and scored Mastery Exam questions use staff with portraits. Mastery includes the other staff in the answer key under **Review-only profiles**.

## Branding

The [National Ability Center website](https://nationalabilitycenter.org/) supplies the header wordmark, icon, and palette.
