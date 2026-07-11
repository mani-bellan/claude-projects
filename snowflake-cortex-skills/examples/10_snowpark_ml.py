"""
10_snowpark_ml.py — Snowpark ML: train, register, and deploy an ML model in Snowflake

Snowpark ML provides scikit-learn-compatible APIs that run inside Snowflake compute,
plus a Model Registry for versioning and deployment as UDFs.

Demonstrates:
  - Feature preprocessing with Snowpark ML Preprocessing
  - Training an XGBoost classifier entirely within Snowflake
  - Logging the model to the Snowflake Model Registry
  - Running batch inference as a vectorized UDF
"""

import os
from dotenv import load_dotenv
from snowflake.snowpark import Session
import snowflake.snowpark.functions as F

load_dotenv()


def get_session() -> Session:
    return Session.builder.configs(
        {
            "account": os.environ["SNOWFLAKE_ACCOUNT"],
            "user": os.environ["SNOWFLAKE_USER"],
            "password": os.environ["SNOWFLAKE_PASSWORD"],
            "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
            "database": os.environ["SNOWFLAKE_DATABASE"],
            "schema": os.environ["SNOWFLAKE_SCHEMA"],
            "role": os.environ.get("SNOWFLAKE_ROLE"),
        }
    ).create()


def train_and_register(session: Session):
    from snowflake.ml.modeling.preprocessing import StandardScaler, OrdinalEncoder
    from snowflake.ml.modeling.xgboost import XGBClassifier
    from snowflake.ml.registry import Registry

    # Load training data (replace with your table)
    df = session.table("churn_features")

    NUMERIC_COLS = ["tenure_months", "monthly_charges", "total_charges"]
    CATEGORICAL_COLS = ["contract_type", "payment_method"]
    LABEL_COL = "churned"
    FEATURE_COLS = NUMERIC_COLS + CATEGORICAL_COLS

    # --- Preprocessing pipeline ---
    scaler = StandardScaler(input_cols=NUMERIC_COLS, output_cols=NUMERIC_COLS)
    encoder = OrdinalEncoder(input_cols=CATEGORICAL_COLS, output_cols=CATEGORICAL_COLS)

    df_scaled = scaler.fit(df).transform(df)
    df_encoded = encoder.fit(df_scaled).transform(df_scaled)

    train_df, test_df = df_encoded.random_split([0.8, 0.2], seed=42)

    # --- Train XGBoost in Snowflake compute ---
    model = XGBClassifier(
        input_cols=FEATURE_COLS,
        label_cols=[LABEL_COL],
        output_cols=["prediction"],
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
    )
    model.fit(train_df)

    # --- Evaluate ---
    predictions = model.predict(test_df)
    accuracy = predictions.filter(F.col("prediction") == F.col(LABEL_COL)).count() / predictions.count()
    print(f"Test accuracy: {accuracy:.4f}")

    # --- Register in Model Registry ---
    registry = Registry(session=session)
    mv = registry.log_model(
        model=model,
        model_name="churn_classifier",
        version_name="v1",
        comment=f"XGBoost churn model — accuracy={accuracy:.4f}",
        metrics={"accuracy": accuracy},
    )
    print(f"Model registered: {mv.model_name} / {mv.version_name}")
    return mv


def batch_inference(session: Session, model_version):
    """Run the registered model as a batch inference job."""
    scoring_df = session.table("churn_features_new")
    results = model_version.run(scoring_df, function_name="predict")
    results.write.save_as_table("churn_predictions", mode="overwrite")
    print(f"Wrote {results.count()} predictions to churn_predictions")


def main():
    session = get_session()

    print("Snowpark ML example — train and register a churn classifier.")
    print("Replace 'churn_features' with your actual table before running.\n")

    # Uncomment to run end-to-end:
    # mv = train_and_register(session)
    # batch_inference(session, mv)

    session.close()


if __name__ == "__main__":
    main()
