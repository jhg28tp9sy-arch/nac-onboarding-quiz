# NAC Connect

A mobile-ready National Ability Center onboarding app with the staff directory, Role Recall, Name Recall, and Mastery Exam. Quiz results stay in the browser session and can be downloaded as CSV.

## Deploy to Streamlit Community Cloud

Deploy from the GitHub repository `jhg28tp9sy-arch/nac-onboarding-quiz`, branch `main`, and main file path `app.py`. The app password controls access to the running Streamlit app. The public GitHub repository contains the roster and portraits.

The default test password is `wyser`. To override it, set the following value under **Settings → Secrets**.

```toml
NAC_DEMO_PASSWORD = "replace-with-your-access-password"
```

## Run locally

Use Python 3.11 or 3.12. To override the test password locally, add the secret to `.streamlit/secrets.toml`.

```sh
pip install -r requirements.txt
streamlit run app.py
python -m unittest discover -s tests -v
```

The app uses the staff roster by default. **Try the fictional demo** switches to six illustrated sample profiles. The local roster manager is disabled by default.

## Branding

The [National Ability Center website](https://nationalabilitycenter.org/) supplies the header wordmark, icon, and palette.
