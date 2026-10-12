from app.db import get_db_connection

MODELS_TO_REGISTER = [
    ("ann", "Artificial Neural Network (Multi-Layer Perceptron) for price direction forecasting", False),
    ("lstm", "Long Short-Term Memory (LSTM) Recurrent Neural Network for sequential price modeling", False),
    ("transformer", "Time-Series Multi-Head Attention Transformer for temporal sequence representation", False),
    ("ensemble", "Ensemble meta-forecaster combining ANN, LSTM, Transformer, Prophet and Baselines", False),
]

def register_models():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for name, desc, base in MODELS_TO_REGISTER:
                cur.execute("""
                    INSERT INTO model (name, description, is_baseline)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
                    RETURNING model_id;
                """, (name, desc, base))
                m_id = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO model_version (model_id, version_tag, parameters)
                    VALUES (%s, 'v1.0.0', '{"architecture": "deep_learning_v1"}'::jsonb)
                    ON CONFLICT (model_id, version_tag) DO NOTHING;
                """, (m_id,))
    print("Models registered successfully!")

if __name__ == "__main__":
    register_models()

