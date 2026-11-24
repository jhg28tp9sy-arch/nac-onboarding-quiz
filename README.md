# NAC Connect demo

A mobile-ready Streamlit demo of the NAC Connect staff directory, Role Recall, Name Recall, and Mastery Exam. The demo opens with six fictional profiles and illustrated portraits. Quiz results stay in the browser session and can be downloaded as CSV.

## Deploy to Streamlit Community Cloud

1. Choose `jhg28tp9sy-arch/nac-onboarding-quiz`, branch `main`, and main file path `app.py`.
2. In **Advanced settings → Secrets**, set a shared demo password using this TOML format.

   ```toml
   NAC_DEMO_PASSWORD = "replace-with-your-demo-password"
   ```

3. Deploy and open the generated Streamlit URL. The password is required before the directory or quizzes open.

This repository is public and its content is fictional. Keep employee data, staff portraits, and internal documents in the private project.

## Run locally

Use Python 3.11 or 3.12. Set `NAC_DEMO_PASSWORD` in your local `.streamlit/secrets.toml` using the format above.

```sh
pip install -r requirements.txt
streamlit run app.py
python -m unittest discover -s tests -v
```

## Branding

The [National Ability Center website](https://nationalabilitycenter.org/) supplies the header wordmark, icon, and palette.
