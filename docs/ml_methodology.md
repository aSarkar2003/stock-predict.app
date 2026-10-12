# ML Methodology & Forecasting Accountability

## 1. Principles of Honest Quantitative Evaluation
1. **Zero Hindsight Information Leakage**: All predictions are computed strictly using market observations timestamped on or before the cutoff date (`price_date <= as_of_date`).
2. **Immutable Append-Only Record**: Once a forecast is generated, it is permanently stored in the `prediction` table. Application users cannot modify or delete predictions.
3. **Paired Sample Benchmarking**: Every model is compared against the trivial `naive_last` ("tomorrow = today") baseline on the exact same set of target dates and tickers.
4. **Sample Size Rigor**: Skill scores and performance conclusions require a minimum of $N \ge 30$ resolved forecasts before being marked as reliable (`is_reliable = TRUE`).

## 2. Direction Classification & Metrics
- **Logarithmic Return**: $r = \ln(P_{\text{target}} / P_{\text{pred}})$
- **Direction Classes**:
  - `UP`: $r > 0.0001$
  - `DOWN`: $r < -0.0001$
  - `FLAT`: $|r| \le 0.0001$
- **Directional Accuracy**: Proportion of predictions where $\text{sign}(\hat{r}) = \text{sign}(r)$.
- **Mean Absolute Error (MAE)**: $\frac{1}{N} \sum |\hat{P} - P|$.
- **Root Mean Squared Error (RMSE)**: $\sqrt{\frac{1}{N} \sum (\hat{P} - P)^2}$.
- **Log Loss**: Cross-entropy over predicted probabilities $\hat{p}$: $-\ln(\hat{p})$ if $r \ge 0$, else $-\ln(1 - \hat{p})$.
- **Skill Score**: $\text{Accuracy}_{\text{model}} - \text{Accuracy}_{\text{baseline}}$.

## 3. Models
1. **`naive_last`**: Assumes tomorrow's price equals today's closing price ($r=0, \text{FLAT}$). Serves as the mandatory baseline.
2. **`drift`**: Predicts forward prices using the historical sample mean log return with volatility-based prediction intervals.
3. **`Prophet` (Experimental)**: Additive time-series model decomposing trend, weekly seasonality, and yearly seasonality. Numeric price forecasts ($\hat{y}$) and uncertainty intervals ($\hat{y}_{\text{lower}}, \hat{y}_{\text{upper}}$) are stored alongside directional predictions.
