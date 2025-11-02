# Advanced Quantitative Research Prompt: Polymarket Whale Copy-Trading System

## ROLE AND CONTEXT

You are an expert quantitative researcher with deep expertise in:
- Prediction market microstructure and dynamics
- Statistical arbitrage and signal generation
- Risk-adjusted performance metrics
- Machine learning for financial time series
- Portfolio optimization theory
- Behavioral finance and information asymmetry

You are analyzing a Polymarket whale copy-trading system with access to:
- 60+ days of historical whale trades (200,000+ transactions)
- Complete market resolution data
- Trader performance metrics across 1,000+ whales
- Real-time trade execution capabilities

## PRIMARY RESEARCH OBJECTIVE

Design a comprehensive, mathematically rigorous framework for:
1. **Whale Quality Scoring**: Multi-factor model to identify profitable traders
2. **Trade Signal Generation**: When and how much to copy
3. **Risk Management**: Position sizing and portfolio constraints
4. **Performance Attribution**: Decompose returns by factor

## DELIVERABLE STRUCTURE

Provide your analysis in the following EXACT format for easy parsing:

```yaml
FORMULA_DEFINITIONS:
  - name: [Formula Name]
    latex: [LaTeX notation]
    python: |
      def formula_name(params):
          # Implementation
          return result
    parameters:
      - name: [param]
        type: [float/int/array]
        description: [what it represents]
    output:
      type: [float/int/array]
      range: [expected range]
      interpretation: [what the output means]

METHODOLOGY_COMPONENTS:
  - component: [Component Name]
    purpose: [Why this component exists]
    inputs: [List of required inputs]
    process: |
      Step-by-step algorithm:
      1. [Step 1]
      2. [Step 2]
    outputs: [What this produces]
    validation: [How to validate correctness]

IMPLEMENTATION_PRIORITY:
  - priority: 1
    component: [Component name]
    rationale: [Why implement first]
    dependencies: []
  - priority: 2
    component: [Component name]
    rationale: [Why implement second]
    dependencies: [List previous components]

RISK_FACTORS:
  - factor: [Risk Factor Name]
    measurement: [How to measure]
    mitigation: [How to mitigate]
    threshold: [Numerical threshold]

BACKTESTING_METRICS:
  - metric: [Metric Name]
    formula: [Formula reference]
    good_range: [Acceptable values]
    excellent_range: [Target values]
    calculation_frequency: [daily/trade/monthly]
```

## SPECIFIC RESEARCH QUESTIONS

### 1. WHALE QUALITY SCORE (0-100)

Design a composite scoring function that weights multiple factors. Consider:

**Performance Factors:**
- Win rate (but account for base rates in different market types)
- Risk-adjusted returns (Sharpe, Sortino, Calmar ratios)
- Consistency metrics (rolling performance stability)
- Drawdown characteristics (depth, duration, recovery)

**Behavioral Factors:**
- Information ratio (returns per unit of tracking error)
- Market timing ability (entry/exit efficiency)
- Position concentration (diversification quality)
- Trading frequency and style consistency

**Market Impact Factors:**
- Average trade size relative to market liquidity
- Price improvement/slippage patterns
- Lead/lag relationships with market moves

**Statistical Significance:**
- Minimum sample size requirements
- Confidence intervals for each metric
- Time-decay weighting for historical performance

Provide:
1. The exact mathematical formula combining these factors
2. Optimal weights derived from historical data analysis
3. Non-linear transformations or caps for each component
4. Normalization method to ensure 0-100 scale

### 2. DYNAMIC POSITION SIZING

Develop an adaptive Kelly Criterion variant that:

**Base Framework:**
- Start with Kelly fraction: f* = (p·b - q)/b
- Where p = win probability, q = loss probability, b = odds

**Adjustments Required:**
- Confidence scaling based on whale's track record length
- Volatility scaling based on recent market regime
- Correlation adjustment for multiple concurrent positions
- Drawdown-based position reduction

**Constraints:**
- Maximum position size (as % of portfolio)
- Maximum positions per whale
- Maximum correlation between positions
- Sector/market type concentration limits

Provide:
1. Modified Kelly formula with all adjustments
2. Parameter estimation methodology
3. Backtested optimal scaling factors
4. Emergency position reduction rules

### 3. TRADE SIGNAL GENERATION

Design a multi-stage filtering system:

**Stage 1: Whale Filter**
```
IF whale_quality_score >= dynamic_threshold
   AND recent_performance > trailing_average
   AND drawdown < max_acceptable
THEN consider_whale
```

**Stage 2: Trade Filter**
```
IF trade_size >= min_whale_commitment
   AND market_liquidity >= min_liquidity
   AND time_to_resolution <= max_horizon
   AND expected_edge >= min_edge
THEN generate_signal
```

**Stage 3: Portfolio Filter**
```
IF correlation_with_existing < max_correlation
   AND total_exposure < max_exposure
   AND sector_concentration < max_concentration
THEN execute_trade
```

Provide:
1. Exact threshold values and their derivation
2. Dynamic adjustment rules for market conditions
3. Signal strength scoring (0-1) for position scaling
4. Minimum holding period and exit conditions

### 4. RISK MANAGEMENT FRAMEWORK

Develop a comprehensive risk system with:

**Portfolio-Level Controls:**
- Value at Risk (VaR) limits
- Expected Shortfall (ES) constraints
- Maximum leverage rules
- Correlation matrix monitoring

**Position-Level Controls:**
- Stop-loss methodology (fixed vs trailing)
- Take-profit targets
- Time-based exits
- Volatility-adjusted position limits

**Whale-Level Controls:**
- Maximum allocation per whale
- Performance-based weight adjustments
- Quarantine rules for underperformers
- Graduation rules for new whales

### 5. PERFORMANCE ATTRIBUTION

Decompose returns into:
- Alpha from whale selection
- Beta from market exposure
- Timing gains/losses
- Risk management impact
- Transaction cost drag

## ADVANCED CONSIDERATIONS

### Market Regime Detection

Provide a method to identify and adapt to:
- High vs low volatility periods
- Trending vs mean-reverting markets
- Event-driven vs normal trading
- Liquidity regimes

### Information Decay

Model how quickly whale edge degrades:
- Half-life of predictive power
- Optimal rebalancing frequency
- Signal staleness indicators

### Adversarial Dynamics

Account for:
- Whales potentially gaming the system
- Capacity constraints as strategy scales
- Market impact of copy-trading

## OUTPUT REQUIREMENTS

1. **Formulas**: Provide complete mathematical notation AND Python implementation
2. **Parameters**: Include specific numerical values, not just ranges
3. **Validation**: Include statistical tests to verify each component
4. **Pseudocode**: Provide step-by-step algorithms for complex processes
5. **Visualization**: Suggest specific charts/metrics to monitor

## EXAMPLE OUTPUT STRUCTURE

```python
# WHALE QUALITY SCORE FORMULA
def calculate_whale_quality_score(whale_metrics):
    """
    Composite scoring function (0-100 scale)

    Components:
    - Win Rate Score (0-25): sigmoid_transform(win_rate, midpoint=0.55, steepness=20)
    - Sharpe Score (0-25): min(25, sharpe_ratio * 8.33)
    - Consistency Score (0-25): rolling_stability_metric
    - Volume Score (0-25): log_transform(total_volume)

    Formula: QS = 0.25*WR + 0.25*SR + 0.25*CS + 0.25*VS
    """
    # Win Rate Component (0-25 points)
    wr_raw = whale_metrics['win_rate']
    wr_score = 25 / (1 + np.exp(-20 * (wr_raw - 0.55)))

    # Sharpe Ratio Component (0-25 points)
    sr_raw = whale_metrics['sharpe_ratio']
    sr_score = min(25, max(0, sr_raw * 8.33))

    # Consistency Component (0-25 points)
    rolling_returns = whale_metrics['rolling_30d_returns']
    consistency = 1 - (np.std(rolling_returns) / np.mean(rolling_returns))
    cs_score = max(0, min(25, consistency * 25))

    # Volume Component (0-25 points)
    volume = whale_metrics['total_volume_usd']
    vs_score = min(25, np.log10(volume / 10000) * 6.25)

    # Composite with non-linear adjustments
    base_score = wr_score + sr_score + cs_score + vs_score

    # Penalty adjustments
    if whale_metrics['max_drawdown'] > 0.30:
        base_score *= 0.8  # 20% penalty for high drawdown

    if whale_metrics['trade_count'] < 50:
        base_score *= 0.7  # 30% penalty for low sample size

    return min(100, max(0, base_score))

# POSITION SIZING FORMULA
def calculate_position_size(whale_score, market_data, portfolio_state):
    """
    Modified Kelly Criterion with multiple adjustments

    Base Kelly: f = (p*b - q)/b
    Adjusted: f_adj = f * confidence * volatility_adj * correlation_adj * drawdown_adj

    Returns: Position size as fraction of portfolio (0.0 to 0.10)
    """
    # Base Kelly calculation
    p = market_data['implied_win_probability']
    b = market_data['decimal_odds'] - 1
    q = 1 - p
    f_kelly = (p * b - q) / b

    # Confidence adjustment (0.2 to 1.0)
    confidence = min(1.0, whale_score / 100 * 1.25)

    # Volatility adjustment (0.5 to 1.0)
    current_vol = market_data['rolling_volatility']
    avg_vol = market_data['average_volatility']
    vol_adj = max(0.5, min(1.0, avg_vol / current_vol))

    # Correlation adjustment (0.3 to 1.0)
    max_correlation = portfolio_state['max_position_correlation']
    corr_adj = max(0.3, 1.0 - max_correlation)

    # Drawdown adjustment (0.5 to 1.0)
    current_dd = portfolio_state['current_drawdown']
    dd_adj = max(0.5, 1.0 - current_dd * 2)

    # Final position size with cap
    f_adjusted = f_kelly * confidence * vol_adj * corr_adj * dd_adj

    # Apply maximum position size constraint (10% of portfolio)
    return min(0.10, max(0.0, f_adjusted))
```

## VALIDATION REQUIREMENTS

For each formula/methodology, provide:

1. **Statistical Validation**:
   - Backtested performance metrics
   - Confidence intervals
   - Robustness tests across different time periods

2. **Economic Intuition**:
   - Why this approach makes sense
   - What market inefficiency it exploits
   - When it might fail

3. **Implementation Complexity**:
   - Computational requirements
   - Data dependencies
   - Update frequency needs

## CRITICAL SUCCESS FACTORS

Your research should optimize for:

1. **Sharpe Ratio > 1.5**: Risk-adjusted returns
2. **Maximum Drawdown < 15%**: Capital preservation
3. **Win Rate > 55%**: Consistency
4. **Capacity > $1M**: Scalability
5. **Latency < 1 second**: Execution speed

## FINAL DELIVERABLE CHECKLIST

Ensure your response includes:

- [ ] Complete mathematical formulas with all parameters specified
- [ ] Python implementations that can be directly executed
- [ ] Specific numerical thresholds derived from data
- [ ] Step-by-step methodology for each component
- [ ] Risk management rules with exact triggers
- [ ] Backtesting framework with success metrics
- [ ] Performance attribution methodology
- [ ] Market regime adaptation rules
- [ ] System monitoring dashboard specifications

Remember: Be specific with numbers, not ranges. For example, say "use 0.73 as the weight" not "use 0.7-0.8 as the weight".


## HOW WE WILL USE THIS PROMPT

1. Feed this prompt to an advanced AI model (GPT-4, Claude, etc.)
2. The AI will generate a structured response following the YAML format
3. Parse the YAML sections to extract formulas and methodologies
4. Implement the Python code directly from the provided snippets
5. Use the validation criteria to verify implementation correctness
6. Monitor using the suggested metrics and thresholds

--- 

END OF PROMPT
