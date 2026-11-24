# NAC Connect

NAC Connect helps new National Ability Center employees learn coworkers’ names, job titles, and departments through an interactive org chart, a searchable staff directory, and three quizzes. Quiz results stay in the browser session and can be downloaded as CSV.

## Deploy to Streamlit Community Cloud

Deploy from the GitHub repository `jhg28tp9sy-arch/nac-onboarding-quiz`, branch `main`, and main file path `app.py`. The app password controls access to the running Streamlit app. The public GitHub repository contains the roster and portraits.

The default test password is `wyser`. To override it, set the following value under **Settings → Secrets**.

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

The org chart uses `data/reporting.json` to link staff IDs to their managers from the Paylocity export. Select a person’s row to expand their reporting branch in place. **Find staff** searches the full roster and can jump from a result to that person’s chart entry. Profiles without a verified reporting link remain searchable.

## Branding

The [National Ability Center website](https://nationalabilitycenter.org/) supplies the header wordmark, icon, and palette.
