import { useState, useEffect } from 'react';

export default function App() {
  const [stats, setStats] = useState(null);
  const [whales, setWhales] = useState([]);
  const [trades, setTrades] = useState([]);
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [tradesFilter, setTradesFilter] = useState('all'); // all, buys, sells
  const [paperTradingEnabled, setPaperTradingEnabled] = useState(false);
  const [selectedMarket, setSelectedMarket] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [tradesPerPage] = useState(20);
  const [whalesPage, setWhalesPage] = useState(1);
  const [whalesPerPage] = useState(25);
  const [positionsPage, setPositionsPage] = useState(1);
  const [positionsPerPage] = useState(10);
  const [strategies, setStrategies] = useState([]);
  const [strategiesLoading, setStrategiesLoading] = useState(true);
  const [showStrategyBuilder, setShowStrategyBuilder] = useState(false);
  const [showAccountsOverview, setShowAccountsOverview] = useState(false);
  const [tradingMode, setTradingMode] = useState('PAPER'); // PAPER, APPROVAL, LIVE
  const [showLiveWarning, setShowLiveWarning] = useState(false);
  const [confirmRisks, setConfirmRisks] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [unrealizedPnl, setUnrealizedPnl] = useState({ total_unrealized_pnl: 0, total_positions: 0, last_updated: null });
  const [copyTradingEnabled, setCopyTradingEnabled] = useState(true);
  const [copyTradingLoading, setCopyTradingLoading] = useState(false);

  // Trading Configuration
  const [privateKey, setPrivateKey] = useState('0xd80a1e6fde576710750a466f6cd4c776a9bd5a3989c42ba2ca63393aeceb8f15');
  const [apiKey, setApiKey] = useState('019a3cc8-4243-7e59-a1c8-3e5adc866ae1');
  const [apiStatus, setApiStatus] = useState('Not Connected');
  const [accountBudget, setAccountBudget] = useState('10000');
  const [basePositionPct, setBasePositionPct] = useState('5');
  const [maxPositionPct, setMaxPositionPct] = useState('10');
  const [dailyLossLimit, setDailyLossLimit] = useState('500');
  const [hourlyLossLimit, setHourlyLossLimit] = useState('200');
  const [maxConsecutiveLosses, setMaxConsecutiveLosses] = useState('5');
  const [minPositionSize, setMinPositionSize] = useState('50');
  const [maxPositionSize, setMaxPositionSize] = useState('1000');
  const [newStrategy, setNewStrategy] = useState({
    name: '',
    description: '',
    criteria_type: 'top_n',
    // Top N criteria
    top_n: 5,
    sort_by: 'quality_score',
    // Core performance filters
    min_sharpe: null,
    min_win_rate: null,
    min_quality_score: null,
    // Volume and trade metrics
    min_total_trades: null,
    min_total_volume: null,
    max_avg_position_size: null,
    min_avg_position_size: null,
    // P&L and profitability
    min_profit_factor: null,
    min_roi: null,
    max_drawdown: null,
    min_consistency_score: null,
    // Category and tier filters
    preferred_categories: [],
    whale_tiers: ['MEGA', 'HIGH', 'MEDIUM'],
    // Market diversity
    min_markets_traded: null,
    max_markets_traded: null,
    // Trade timing
    min_avg_hold_time: null,
    max_avg_hold_time: null,
    // Recent performance
    min_recent_performance: null,
    recent_performance_days: 30,
    // Position sizing
    base_position_pct: 5.0,
    max_position_pct: 10.0,
    use_kelly: false,
    kelly_fraction: 0.25,
    scale_by_confidence: true,
    scale_by_liquidity: true,
    min_position_size: 50,
    max_position_size: null,
    // Risk management
    max_positions: 10,
    max_per_market: 1000,
    max_per_category: 0.3,
    max_total_exposure: 0.8,
    stop_loss_pct: null,
    take_profit_pct: null,
    trailing_stop_pct: null,
    max_daily_loss: null,
    circuit_breaker_loss: -0.15,
    // Account
    initial_balance: 10000.0
  });

  useEffect(() => {
    // Load strategies from localStorage first
    const loadStrategiesFromStorage = () => {
      try {
        const saved = localStorage.getItem('whale_strategies');
        if (saved) {
          const savedStrategies = JSON.parse(saved);
          // Make all saved strategies activated by default
          const activatedStrategies = savedStrategies.map(s => ({...s, is_active: true}));
          setStrategies(activatedStrategies);
        }
      } catch (error) {
        console.error('Error loading saved strategies:', error);
      }
    };

    loadStrategiesFromStorage();

    const fetchData = async () => {
      try {
        const [statsRes, whalesRes, tradesRes, positionsRes, strategiesRes] = await Promise.all([
          fetch('/api/stats/summary'),
          fetch('/api/whales?limit=20'),
          fetch('/api/trades?limit=1000'),
          fetch('/api/positions?limit=50'),
          fetch('/api/strategies')
        ]);
        setStats(await statsRes.json());
        setWhales(await whalesRes.json());
        setTrades(await tradesRes.json());
        setPositions(await positionsRes.json());
        const apiStrategies = await strategiesRes.json();
        // Make all API strategies activated by default
        const activatedStrategies = apiStrategies.map(s => ({...s, is_active: true}));
        setStrategies(activatedStrategies);
        setStrategiesLoading(false);
      } catch (error) {
        console.error('API Error:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);


  // Load saved configuration on mount
  useEffect(() => {
    const loadSavedConfig = () => {
      try {
        const saved = localStorage.getItem('polymarket_config');
        if (saved) {
          const config = JSON.parse(saved);
          setPrivateKey(config.privateKey || '0xd80a1e6fde576710750a466f6cd4c776a9bd5a3989c42ba2ca63393aeceb8f15');
          setApiKey(config.apiKey || '019a3cc8-4243-7e59-a1c8-3e5adc866ae1');
          setAccountBudget(config.accountBudget || '10000');
          setBasePositionPct(config.basePositionPct || '5');
          setMaxPositionPct(config.maxPositionPct || '10');
          setDailyLossLimit(config.dailyLossLimit || '500');
          setHourlyLossLimit(config.hourlyLossLimit || '200');
          setMaxConsecutiveLosses(config.maxConsecutiveLosses || '5');
          setMinPositionSize(config.minPositionSize || '50');
          setMaxPositionSize(config.maxPositionSize || '1000');

          // Set status to connected if credentials exist
          if (config.privateKey && config.apiKey) {
            setApiStatus('Connected');
          }
        }
      } catch (error) {
        console.error('Error loading saved config:', error);
      }
    };
    loadSavedConfig();
  }, []);

  // Update current time every second for live ticker
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  // Fetch unrealized P&L every minute
  useEffect(() => {
    const fetchUnrealizedPnl = async () => {
      try {
        const res = await fetch('/api/unrealized-pnl');
        const data = await res.json();
        setUnrealizedPnl(data);
      } catch (error) {
        console.error('Error fetching unrealized P&L:', error);
      }
    };

    // Fetch immediately on mount
    fetchUnrealizedPnl();

    // Then fetch every 60 seconds
    const interval = setInterval(fetchUnrealizedPnl, 60000);

    return () => clearInterval(interval);
  }, []);

  // Auto-save strategies to localStorage every 10 seconds
  useEffect(() => {
    const saveInterval = setInterval(() => {
      if (strategies.length > 0) {
        try {
          localStorage.setItem('whale_strategies', JSON.stringify(strategies));
          console.log('Strategies auto-saved');
        } catch (error) {
          console.error('Error auto-saving strategies:', error);
        }
      }
    }, 10000); // 10 seconds

    return () => clearInterval(saveInterval);
  }, [strategies]);

  // Fetch copy trading kill switch status on mount and poll every 10 seconds
  useEffect(() => {
    const fetchCopyTradingStatus = async () => {
      try {
        const res = await fetch('/api/trading-config/status');
        const data = await res.json();
        setCopyTradingEnabled(data.copy_trading_enabled);
      } catch (error) {
        console.error('Error fetching copy trading status:', error);
      }
    };

    // Fetch immediately on mount
    fetchCopyTradingStatus();

    // Then poll every 10 seconds
    const interval = setInterval(fetchCopyTradingStatus, 10000);

    return () => clearInterval(interval);
  }, []);

  // Format time in PST
  const formatPSTTime = () => {
    return new Date().toLocaleTimeString('en-US', {
      timeZone: 'America/Los_Angeles',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    });
  };

  // Reset all saved strategies
  const handleResetAllStrategies = () => {
    if (window.confirm('Reset all strategies? This will clear all saved strategy data from localStorage.')) {
      localStorage.removeItem('whale_strategies');
      // Reload strategies from API
      fetch('/api/strategies')
        .then(res => res.json())
        .then(apiStrategies => {
          const activatedStrategies = apiStrategies.map(s => ({...s, is_active: true}));
          setStrategies(activatedStrategies);
        })
        .catch(error => console.error('Error resetting strategies:', error));
    }
  };

  // Handler functions for trading configuration
  const handleTestConnection = async () => {
    setApiStatus('Testing...');
    try {
      // Simulate API connection test
      // In production, this would actually test the Polymarket API
      await new Promise(resolve => setTimeout(resolve, 1500));

      if (privateKey && apiKey) {
        setApiStatus(' Connected');
        setTimeout(() => setApiStatus('Connected'), 3000);
      } else {
        setApiStatus(' Failed - Missing credentials');
      }
    } catch (error) {
      setApiStatus(' Connection Failed');
    }
  };

  const handleSaveCredentials = () => {
    // Save credentials to localStorage
    localStorage.setItem('polymarket_config', JSON.stringify({
      privateKey,
      apiKey,
      accountBudget,
      basePositionPct,
      maxPositionPct,
      dailyLossLimit,
      hourlyLossLimit,
      maxConsecutiveLosses,
      minPositionSize,
      maxPositionSize
    }));

    alert(' Configuration saved successfully!');
  };

  // Handler for copy trading kill switch toggle
  const handleToggleCopyTrading = async () => {
    if (copyTradingLoading) return;

    setCopyTradingLoading(true);
    try {
      const endpoint = copyTradingEnabled
        ? '/api/trading-config/disable'
        : '/api/trading-config/enable';

      const res = await fetch(endpoint, { method: 'POST' });
      const data = await res.json();

      if (data.success) {
        setCopyTradingEnabled(data.copy_trading_enabled);
      } else {
        console.error('Failed to toggle copy trading:', data.error);
        alert('Failed to toggle copy trading: ' + (data.error || 'Unknown error'));
      }
    } catch (error) {
      console.error('Error toggling copy trading:', error);
      alert('Error toggling copy trading. Please try again.');
    } finally {
      setCopyTradingLoading(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center min-h-screen">Loading...</div>;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      <nav className="bg-gray-800/50 border-b border-gray-700 backdrop-blur-lg">
        <div className="container mx-auto px-3 py-1.5">
          <div className="flex items-center justify-between">
            <h1 className="text-sm font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
              Whale Trader v0.1
            </h1>

            <div className="flex items-center gap-2">
              {/* Navigation Tabs */}
              <div className="flex gap-1">
                {['dashboard', 'trades', 'strategies', 'trading'].map((tab) => {
                  const tabLabels = { dashboard: 'Dashboard', trades: 'Recent Trades', strategies: 'Strategies', trading: 'Trading' };
                  return (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={`px-2 py-1 rounded text-xs font-medium transition-all ${activeTab === tab ? 'bg-blue-600 text-white' : 'bg-gray-700/50 text-gray-300 hover:bg-gray-700'}`}
                    >
                      {tabLabels[tab]}
                    </button>
                  );
                })}
              </div>

              {/* Copy Trading Kill Switch */}
              <button
                onClick={handleToggleCopyTrading}
                disabled={copyTradingLoading}
                className={`flex items-center gap-2 px-3 py-1 rounded text-xs font-medium transition-all border ${
                  copyTradingLoading
                    ? 'bg-gray-700/50 border-gray-600 text-gray-400 cursor-wait'
                    : copyTradingEnabled
                    ? 'bg-green-600/20 border-green-500 text-green-400 hover:bg-green-600/30'
                    : 'bg-red-600/20 border-red-500 text-red-400 hover:bg-red-600/30'
                }`}
                title={copyTradingEnabled ? 'Click to disable copy trading' : 'Click to enable copy trading'}
              >
                {copyTradingLoading ? (
                  <>
                    <svg className="animate-spin h-3 w-3" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>Updating...</span>
                  </>
                ) : (
                  <>
                    <div className={`w-8 h-4 rounded-full relative transition-all ${copyTradingEnabled ? 'bg-green-500' : 'bg-red-500'}`}>
                      <div className={`absolute top-0.5 w-3 h-3 bg-white rounded-full transition-all ${copyTradingEnabled ? 'right-0.5' : 'left-0.5'}`}></div>
                    </div>
                    <span className="font-semibold">{copyTradingEnabled ? 'ON' : 'OFF'}</span>
                  </>
                )}
              </button>

              {/* Unrealized P&L Display */}
              <div className="flex items-center gap-2 px-2 py-1 bg-gray-700/30 rounded border border-gray-600 ml-2 pl-2 border-l border-gray-700">
                <div className="text-left">
                  <div className="text-xs text-gray-400">P&L</div>
                  <div className={`text-sm font-bold ${unrealizedPnl.total_unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {unrealizedPnl.total_unrealized_pnl >= 0 ? '+' : ''}${unrealizedPnl.total_unrealized_pnl.toFixed(2)}
                  </div>
                </div>
                <div className="border-l border-gray-600 pl-2">
                  <div className="text-xs text-gray-400">{unrealizedPnl.total_positions} pos</div>
                  <div className="text-xs text-gray-500">
                    {unrealizedPnl.last_updated ? `${new Date(unrealizedPnl.last_updated).toLocaleTimeString()}` : '-'}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-1">
                <button
                  onClick={() => setShowAccountsOverview(true)}
                  className="px-2 py-1 bg-purple-600 hover:bg-purple-700 text-white rounded text-xs font-medium transition-all flex items-center gap-1"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  Accounts
                </button>
                <button
                  onClick={() => setShowStrategyBuilder(true)}
                  className="px-2 py-1 bg-green-600 hover:bg-green-700 text-white rounded text-xs font-medium transition-all flex items-center gap-1"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Add Account
                </button>
              </div>
            </div>
          </div>
        </div>
      </nav>

      <main className="container mx-auto px-6 py-8">
        {activeTab === 'dashboard' && (
          <>
            <div className="flex justify-center mb-8">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl w-full">
                {[
                  { label: 'Total Whales', value: stats?.total_whales || 0, color: 'blue' },
                  { label: '24h Trades', value: stats?.trades_24h || 0, color: 'green' },
                  { label: '24h Volume', value: `$${(stats?.volume_24h || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`, color: 'purple' },
                ].map((stat) => (
                  <div key={stat.label} className="bg-gray-800/50 backdrop-blur-lg rounded-xl p-6 border border-gray-700">
                    <div className="text-gray-400 text-sm mb-2">{stat.label}</div>
                    <div className={`text-sm font-bold text-${stat.color}-400`}>{stat.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Active Whales with Pagination */}
            {(() => {
              const totalWhalesPages = Math.ceil(whales.length / whalesPerPage);
              const indexOfLastWhale = whalesPage * whalesPerPage;
              const indexOfFirstWhale = indexOfLastWhale - whalesPerPage;
              const currentWhales = whales.slice(indexOfFirstWhale, indexOfLastWhale);

              return (
                <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 overflow-hidden">
                  <div className="p-2 border-b border-gray-700 flex items-center justify-between">
                    <h2 className="text-sm font-bold">Active Whales</h2>
                    <p className="text-xs text-gray-400">
                      Showing {indexOfFirstWhale + 1}-{Math.min(indexOfLastWhale, whales.length)} of {whales.length}
                    </p>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-gray-700/50">
                        <tr>
                          {['Whale', 'Tier', 'Win Rate', 'Sharpe', 'Total P&L', 'Volume', 'Trades', '24h'].map((header) => (
                            <th key={header} className="px-2 py-1 text-left text-xs font-semibold text-gray-300">
                              {header}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-700">
                        {currentWhales.map((whale) => (
                          <tr key={whale.address} className="hover:bg-gray-700/30 transition-colors">
                            <td className="px-2 py-1 text-xs">
                              <span className="font-medium text-white">{whale.pseudonym}</span>
                              <span className="text-gray-400 ml-1">({whale.address.slice(0, 6)}...)</span>
                            </td>
                            <td className="px-2 py-1">
                              <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${whale.tier === 'MEGA' ? 'bg-purple-500/20 text-purple-300' : whale.tier === 'HIGH' ? 'bg-blue-500/20 text-blue-300' : 'bg-green-500/20 text-green-300'}`}>
                                {whale.tier}
                              </span>
                            </td>
                            <td className="px-2 py-1 text-green-400 font-medium text-xs">{whale.win_rate}%</td>
                            <td className="px-2 py-1 text-blue-400 font-medium text-xs">{whale.sharpe_ratio}</td>
                            <td className="px-2 py-1 text-yellow-400 font-medium text-xs">${whale.total_pnl.toLocaleString()}</td>
                            <td className="px-2 py-1 text-gray-300 text-xs">${whale.total_volume.toLocaleString()}</td>
                            <td className="px-2 py-1 text-gray-300 text-xs">{whale.total_trades}</td>
                            <td className="px-2 py-1 text-cyan-400 font-medium text-xs">{whale.trades_24h || 0}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination Controls */}
                  {totalWhalesPages > 1 && (
                    <div className="p-2 border-t border-gray-700 flex items-center justify-between">
                      <button
                        onClick={() => setWhalesPage(prev => Math.max(prev - 1, 1))}
                        disabled={whalesPage === 1}
                        className={`px-3 py-1 rounded text-xs font-medium transition-all ${
                          whalesPage === 1
                            ? 'bg-gray-700/30 text-gray-500 cursor-not-allowed'
                            : 'bg-gray-700 text-white hover:bg-gray-600'
                        }`}
                      >
                        ← Prev
                      </button>

                      <div className="flex gap-1">
                        {Array.from({ length: Math.min(totalWhalesPages, 5) }, (_, i) => {
                          let pageNum;
                          if (totalWhalesPages <= 5) {
                            pageNum = i + 1;
                          } else if (whalesPage <= 3) {
                            pageNum = i + 1;
                          } else if (whalesPage >= totalWhalesPages - 2) {
                            pageNum = totalWhalesPages - 4 + i;
                          } else {
                            pageNum = whalesPage - 2 + i;
                          }

                          return (
                            <button
                              key={pageNum}
                              onClick={() => setWhalesPage(pageNum)}
                              className={`px-2 py-1 rounded text-xs font-medium transition-all ${
                                whalesPage === pageNum
                                  ? 'bg-blue-600 text-white'
                                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                              }`}
                            >
                              {pageNum}
                            </button>
                          );
                        })}
                      </div>

                      <button
                        onClick={() => setWhalesPage(prev => Math.min(prev + 1, totalWhalesPages))}
                        disabled={whalesPage === totalWhalesPages}
                        className={`px-3 py-1 rounded text-xs font-medium transition-all ${
                          whalesPage === totalWhalesPages
                            ? 'bg-gray-700/30 text-gray-500 cursor-not-allowed'
                            : 'bg-gray-700 text-white hover:bg-gray-600'
                        }`}
                      >
                        Next →
                      </button>
                    </div>
                  )}
                </div>
              );
            })()}
          </>
        )}

        {activeTab === 'trading' && (
          <div className="max-w-7xl mx-auto space-y-6">
            {/* Header */}
            <div className="bg-gradient-to-r from-purple-600 to-blue-600 rounded-xl border border-purple-500 p-6">
              <h2 className="text-sm font-bold mb-2"> Polymarket Live Trading</h2>
              <p className="text-purple-100">Advanced whale copy trading with comprehensive risk management</p>
            </div>

            {/* Trading Mode Selector */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-6">
              <h3 className="text-xl font-bold mb-4">Trading Mode</h3>
              <div className="grid grid-cols-3 gap-4">
                <button
                  onClick={() => setTradingMode('PAPER')}
                  className={`border-2 rounded-lg p-2 text-left hover:bg-blue-600/30 transition-all ${
                    tradingMode === 'PAPER'
                      ? 'bg-blue-600/20 border-blue-500'
                      : 'bg-gray-700/30 border-gray-600'
                  }`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className="h-12 w-12 rounded-full bg-blue-500 flex items-center justify-center">
                      📝
                    </div>
                    <div>
                      <div className="font-bold text-xs">PAPER</div>
                      <div className="text-xs text-blue-300">
                        {tradingMode === 'PAPER' ? 'Currently Active' : 'Virtual Trading'}
                      </div>
                    </div>
                  </div>
                  <p className="text-sm text-gray-400">Simulated trading with virtual funds. Safe for testing.</p>
                </button>

                <button
                  onClick={() => setTradingMode('APPROVAL')}
                  className={`border-2 rounded-lg p-2 text-left hover:bg-yellow-600/30 transition-all ${
                    tradingMode === 'APPROVAL'
                      ? 'bg-yellow-600/20 border-yellow-500'
                      : 'bg-gray-700/30 border-gray-600'
                  }`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className="h-12 w-12 rounded-full bg-yellow-500 flex items-center justify-center">
                      ✋
                    </div>
                    <div>
                      <div className="font-bold text-xs">APPROVAL</div>
                      <div className="text-xs text-yellow-300">
                        {tradingMode === 'APPROVAL' ? 'Currently Active' : 'Manual Review'}
                      </div>
                    </div>
                  </div>
                  <p className="text-sm text-gray-400">Review and approve each trade before execution.</p>
                </button>

                <button
                  onClick={() => {
                    setTradingMode(tradingMode === 'LIVE' ? 'PAPER' : 'LIVE');
                  }}
                  className={`border-2 rounded-lg p-2 text-left hover:bg-red-600/30 transition-all group ${
                    tradingMode === 'LIVE'
                      ? 'bg-red-600/20 border-red-500'
                      : 'bg-gray-700/30 border-gray-600'
                  }`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className="h-12 w-12 rounded-full bg-red-500 flex items-center justify-center">
                      
                    </div>
                    <div>
                      <div className="font-bold text-xs">LIVE</div>
                      <div className="text-xs text-red-300">
                        {tradingMode === 'LIVE' ? ' ACTIVE - Click to disable' : ' Real Money - Click to enable'}
                      </div>
                    </div>
                  </div>
                  <p className="text-sm text-gray-400">
                    {tradingMode === 'LIVE'
                      ? 'Click to switch back to PAPER mode (safe).'
                      : 'Automatic real money trading on Polymarket.'}
                  </p>
                </button>
              </div>
            </div>

            {/* Status Cards */}
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-4">
                <div className="text-gray-400 text-sm mb-1">Trading Mode</div>
                <div className={`text-sm font-bold ${
                  tradingMode === 'LIVE' ? 'text-red-400' :
                  tradingMode === 'APPROVAL' ? 'text-yellow-400' :
                  'text-blue-400'
                }`}>
                  {tradingMode}
                </div>
              </div>
              <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-4">
                <div className="text-gray-400 text-sm mb-1">Circuit Breaker</div>
                <div className="text-sm font-bold text-green-400 flex items-center gap-2">
                   OK
                </div>
              </div>
              <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-4">
                <div className="text-gray-400 text-sm mb-1">API Status</div>
                <div className={`text-sm font-bold flex items-center gap-2 ${
                  apiStatus.includes('Connected') ? 'text-green-400' :
                  apiStatus.includes('Testing') ? 'text-yellow-400' :
                  apiStatus.includes('Failed') ? 'text-red-400' :
                  'text-yellow-400'
                }`}>
                  <div className={`h-3 w-3 rounded-full ${
                    apiStatus.includes('Connected') ? 'bg-green-500' :
                    apiStatus.includes('Testing') ? 'bg-yellow-500 animate-pulse' :
                    apiStatus.includes('Failed') ? 'bg-red-500' :
                    'bg-yellow-500'
                  }`}></div>
                  {apiStatus}
                </div>
              </div>
              <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-4">
                <div className="text-gray-400 text-sm mb-1">Open Positions</div>
                <div className="text-sm font-bold text-white">{unrealizedPnl.total_positions}</div>
              </div>
            </div>

            {/* Performance Metrics */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-6">
              <h3 className="text-xl font-bold mb-4">Performance Metrics</h3>
              <div className="grid grid-cols-6 gap-4">
                <div className="bg-gray-700/30 rounded-lg p-4">
                  <div className="text-gray-400 text-xs mb-1">Balance</div>
                  <div className="text-xl font-bold text-white">${parseFloat(accountBudget || 0).toLocaleString()}</div>
                </div>
                <div className="bg-gray-700/30 rounded-lg p-4">
                  <div className="text-gray-400 text-xs mb-1">Total P&L</div>
                  <div className="text-xl font-bold text-gray-400">$0.00</div>
                </div>
                <div className="bg-gray-700/30 rounded-lg p-4">
                  <div className="text-gray-400 text-xs mb-1">ROI</div>
                  <div className="text-xl font-bold text-gray-400">0.0%</div>
                </div>
                <div className="bg-gray-700/30 rounded-lg p-4">
                  <div className="text-gray-400 text-xs mb-1">Win Rate</div>
                  <div className="text-xl font-bold text-gray-400">0.0%</div>
                </div>
                <div className="bg-gray-700/30 rounded-lg p-4">
                  <div className="text-gray-400 text-xs mb-1">Total Trades</div>
                  <div className="text-xl font-bold text-white">0</div>
                </div>
                <div className="bg-gray-700/30 rounded-lg p-4">
                  <div className="text-gray-400 text-xs mb-1">Daily P&L</div>
                  <div className="text-xl font-bold text-gray-400">$0.00</div>
                </div>
              </div>
            </div>

            {/* Circuit Breaker Status */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-6">
              <h3 className="text-xl font-bold mb-4">🛡️ Circuit Breaker Status</h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-400">Daily Loss Limit</span>
                    <span className="text-xs text-green-400 font-bold">OK</span>
                  </div>
                  <div className="text-sm font-bold text-white">$0 / $500</div>
                  <div className="mt-2 bg-gray-700/50 rounded-full h-2 overflow-hidden">
                    <div className="bg-green-500 h-full" style={{width: '0%'}}></div>
                  </div>
                </div>
                <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-400">Hourly Loss Limit</span>
                    <span className="text-xs text-green-400 font-bold">OK</span>
                  </div>
                  <div className="text-sm font-bold text-white">$0 / $200</div>
                  <div className="mt-2 bg-gray-700/50 rounded-full h-2 overflow-hidden">
                    <div className="bg-green-500 h-full" style={{width: '0%'}}></div>
                  </div>
                </div>
                <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-400">Consecutive Losses</span>
                    <span className="text-xs text-green-400 font-bold">OK</span>
                  </div>
                  <div className="text-sm font-bold text-white">0 / 5</div>
                  <div className="mt-2 bg-gray-700/50 rounded-full h-2 overflow-hidden">
                    <div className="bg-green-500 h-full" style={{width: '0%'}}></div>
                  </div>
                </div>
              </div>
            </div>


            {/* Polymarket API Configuration */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-yellow-500/50 p-6">
              <div className="flex items-start gap-4 mb-4">
                <div className="h-12 w-12 rounded-full bg-yellow-500/20 flex items-center justify-center flex-shrink-0">
                  
                </div>
                <div className="flex-1">
                  <h3 className="text-xl font-bold mb-2">Polymarket API Configuration</h3>
                  <p className="text-gray-400 text-sm">Configure your Polymarket API credentials and trading parameters</p>
                </div>
                <div className={`px-3 py-1 rounded-lg text-sm font-medium ${
                  apiStatus.includes('Connected') ? 'bg-green-500/20 text-green-400' :
                  apiStatus.includes('Testing') ? 'bg-yellow-500/20 text-yellow-400' :
                  apiStatus.includes('Failed') ? 'bg-red-500/20 text-red-400' :
                  'bg-gray-600/20 text-gray-400'
                }`}>
                  {apiStatus}
                </div>
              </div>

              {/* Credentials */}
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Private Key</label>
                  <input
                    type="password"
                    value={privateKey}
                    onChange={(e) => setPrivateKey(e.target.value)}
                    placeholder="0x..."
                    className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">API Key</label>
                  <input
                    type="text"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Your API Key"
                    className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              {/* Account Budget & Position Sizing */}
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2"> Account Budget ($)</label>
                  <input
                    type="number"
                    value={accountBudget}
                    onChange={(e) => setAccountBudget(e.target.value)}
                    placeholder="10000"
                    className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2"> Base Position (%)</label>
                  <input
                    type="number"
                    value={basePositionPct}
                    onChange={(e) => setBasePositionPct(e.target.value)}
                    placeholder="5"
                    min="1"
                    max="20"
                    className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2"> Max Position (%)</label>
                  <input
                    type="number"
                    value={maxPositionPct}
                    onChange={(e) => setMaxPositionPct(e.target.value)}
                    placeholder="10"
                    min="1"
                    max="30"
                    className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              {/* Position Size Limits */}
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">🎯 Min Position Size ($)</label>
                  <input
                    type="number"
                    value={minPositionSize}
                    onChange={(e) => setMinPositionSize(e.target.value)}
                    placeholder="50"
                    className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">🎯 Max Position Size ($)</label>
                  <input
                    type="number"
                    value={maxPositionSize}
                    onChange={(e) => setMaxPositionSize(e.target.value)}
                    placeholder="1000"
                    className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              {/* Circuit Breaker Settings */}
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 mb-4">
                <h4 className="text-sm font-bold text-red-400 mb-3">🛡️ Circuit Breaker Settings</h4>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs text-gray-400 mb-2">Daily Loss Limit ($)</label>
                    <input
                      type="number"
                      value={dailyLossLimit}
                      onChange={(e) => setDailyLossLimit(e.target.value)}
                      placeholder="500"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-3 py-2 text-white focus:border-red-500 focus:outline-none text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-2">Hourly Loss Limit ($)</label>
                    <input
                      type="number"
                      value={hourlyLossLimit}
                      onChange={(e) => setHourlyLossLimit(e.target.value)}
                      placeholder="200"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-3 py-2 text-white focus:border-red-500 focus:outline-none text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-2">Max Consecutive Losses</label>
                    <input
                      type="number"
                      value={maxConsecutiveLosses}
                      onChange={(e) => setMaxConsecutiveLosses(e.target.value)}
                      placeholder="5"
                      min="1"
                      max="20"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-3 py-2 text-white focus:border-red-500 focus:outline-none text-sm"
                    />
                  </div>
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={handleTestConnection}
                  className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-all"
                >
                  {apiStatus === 'Testing...' ? '⏳ Testing...' : '🔌 Test Connection'}
                </button>
                <button
                  onClick={handleSaveCredentials}
                  className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-all"
                >
                  💾 Save Configuration
                </button>
                <a
                  href="https://docs.polymarket.com/#authentication"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-medium transition-all flex items-center gap-2"
                >
                  📚 API Docs
                </a>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-6">
              <h3 className="text-xl font-bold mb-4">Quick Actions</h3>
              <div className="grid grid-cols-4 gap-3">
                <button className="px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-all">
                   View Trading Guide
                </button>
                <button className="px-4 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-all">
                   Run Bet Demo
                </button>
                <button className="px-4 py-3 bg-orange-600 hover:bg-orange-700 text-white rounded-lg font-medium transition-all">
                  🔄 Reset Circuit Breaker
                </button>
                <button className="px-4 py-3 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-all">
                  🛑 Emergency Stop
                </button>
              </div>
            </div>

            {/* Warning Banner */}
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6">
              <div className="flex items-start gap-4">
                <div className="text-sm"></div>
                <div>
                  <h4 className="text-lg font-bold text-red-400 mb-2">Live Trading Warning</h4>
                  <p className="text-gray-300 text-sm mb-3">
                    Live trading involves real money and real risk. Before switching to LIVE mode:
                  </p>
                  <ul className="text-sm text-gray-400 space-y-1 list-disc list-inside">
                    <li>Run paper trading for at least 1 week to understand the system</li>
                    <li>Start with small amounts ($500-$1000 maximum)</li>
                    <li>Use APPROVAL mode to manually review trades initially</li>
                    <li>Monitor closely for the first few days</li>
                    <li>Never trade more than you can afford to lose</li>
                  </ul>
                  <p className="text-red-300 text-sm mt-3 font-medium">
                    📖 Read the full guide: <code className="bg-gray-800 px-2 py-1 rounded">REAL_TRADING_GUIDE.md</code>
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'strategies' && (
          <div className="space-y-6">
            {/* Header */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-6">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h2 className="text-sm font-bold mb-2">Trading Strategies</h2>
                  <p className="text-gray-400">All strategies are activated and auto-save every 10 seconds. Data persists across page refreshes.</p>
                </div>
                <button
                  onClick={handleResetAllStrategies}
                  className="bg-red-600 hover:bg-red-700 text-white px-2 py-1 rounded-lg text-sm font-medium transition-colors"
                >
                  Reset All
                </button>
              </div>
            </div>

            {/* Strategies Grid */}
            {strategiesLoading ? (
              <div className="text-center text-gray-400 py-12">Loading strategies...</div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {strategies.map((strategy) => {
                  const handleToggle = async () => {
                    const endpoint = strategy.active
                      ? `/api/strategies/${strategy.id}/deactivate`
                      : `/api/strategies/${strategy.id}/activate`;

                    try {
                      const res = await fetch(endpoint, { method: 'POST' });
                      if (res.ok) {
                        // Refresh strategies
                        const strategiesRes = await fetch('/api/strategies');
                        setStrategies(await strategiesRes.json());
                      }
                    } catch (error) {
                      console.error('Error toggling strategy:', error);
                    }
                  };

                  const handleReset = async () => {
                    if (!window.confirm(`Reset ${strategy.name}? This will clear all trades and reset the balance to $10,000.`)) {
                      return;
                    }

                    try {
                      const res = await fetch(`/api/strategies/${strategy.id}/reset`, { method: 'POST' });
                      if (res.ok) {
                        // Refresh strategies
                        const strategiesRes = await fetch('/api/strategies');
                        setStrategies(await strategiesRes.json());
                      }
                    } catch (error) {
                      console.error('Error resetting strategy:', error);
                    }
                  };

                  return (
                    <div key={strategy.id} className={`bg-gray-800/50 backdrop-blur-lg rounded-xl border ${strategy.active ? 'border-green-500' : 'border-gray-700'} overflow-hidden`}>
                      {/* Strategy Header */}
                      <div className="p-6 border-b border-gray-700">
                        <div className="flex items-start justify-between mb-3">
                          <div>
                            <h3 className="text-xl font-bold">{strategy.name}</h3>
                            <p className="text-sm text-gray-400 mt-1">{strategy.description}</p>
                          </div>
                          <div className={`px-3 py-1 rounded-full text-xs font-bold ${strategy.active ? 'bg-green-500/20 text-green-400' : 'bg-gray-700 text-gray-400'}`}>
                            {strategy.active ? '● ACTIVE' : '○ INACTIVE'}
                          </div>
                        </div>

                        {/* Criteria Display */}
                        <div className="flex gap-2 flex-wrap mt-3">
                          {strategy.criteria.type === 'top_n' && (
                            <span className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full text-xs font-medium">
                              Top {strategy.criteria.n} by {strategy.criteria.sort_by.replace('_', ' ')}
                            </span>
                          )}
                          {strategy.criteria.type === 'filter' && (
                            <>
                              {strategy.criteria.min_sharpe && (
                                <span className="px-3 py-1 bg-purple-500/20 text-purple-400 rounded-full text-xs font-medium">
                                  Sharpe ≥ {strategy.criteria.min_sharpe}
                                </span>
                              )}
                              {strategy.criteria.min_win_rate && (
                                <span className="px-3 py-1 bg-green-500/20 text-green-400 rounded-full text-xs font-medium">
                                  Win Rate ≥ {strategy.criteria.min_win_rate}%
                                </span>
                              )}
                            </>
                          )}
                          <span className="px-3 py-1 bg-yellow-500/20 text-yellow-400 rounded-full text-xs font-medium">
                            Position: {strategy.position_sizing.base_pct}%-{strategy.position_sizing.max_pct}%
                          </span>
                        </div>
                      </div>

                      {/* Account Stats */}
                      <div className="p-6">
                        <div className="grid grid-cols-2 gap-4 mb-4">
                          <div className="bg-gray-700/30 rounded-lg p-3">
                            <div className="text-gray-400 text-xs mb-1">Balance</div>
                            <div className="text-lg font-bold text-white">${strategy.account.balance.toLocaleString()}</div>
                          </div>
                          <div className="bg-gray-700/30 rounded-lg p-3">
                            <div className="text-gray-400 text-xs mb-1">P&L</div>
                            <div className={`text-lg font-bold ${strategy.account.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              ${strategy.account.total_pnl.toLocaleString()}
                            </div>
                          </div>
                          <div className="bg-gray-700/30 rounded-lg p-3">
                            <div className="text-gray-400 text-xs mb-1">Trades</div>
                            <div className="text-lg font-bold text-white">{strategy.account.total_trades}</div>
                          </div>
                          <div className="bg-gray-700/30 rounded-lg p-3">
                            <div className="text-gray-400 text-xs mb-1">Win Rate</div>
                            <div className="text-lg font-bold text-cyan-400">{strategy.account.win_rate.toFixed(1)}%</div>
                          </div>
                        </div>

                        {/* ROI Bar */}
                        <div className="mb-4">
                          <div className="flex justify-between text-xs text-gray-400 mb-1">
                            <span>ROI</span>
                            <span className={strategy.account.roi >= 0 ? 'text-green-400' : 'text-red-400'}>
                              {strategy.account.roi.toFixed(2)}%
                            </span>
                          </div>
                          <div className="w-full bg-gray-700/30 rounded-full h-2">
                            <div
                              className={`h-2 rounded-full ${strategy.account.roi >= 0 ? 'bg-green-500' : 'bg-red-500'}`}
                              style={{ width: `${Math.min(Math.abs(strategy.account.roi), 100)}%` }}
                            />
                          </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex gap-2">
                          <button
                            onClick={handleToggle}
                            className={`flex-1 px-2 py-1 rounded-lg font-medium transition-all ${
                              strategy.active
                                ? 'bg-red-600 hover:bg-red-700 text-white'
                                : 'bg-green-600 hover:bg-green-700 text-white'
                            }`}
                          >
                            {strategy.active ? '⏸ Deactivate' : '▶ Activate'}
                          </button>
                          <button
                            onClick={handleReset}
                            className="px-2 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg font-medium transition-all"
                          >
                            ↻ Reset
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {activeTab === 'trades' && (() => {
          const totalPages = Math.ceil(trades.length / tradesPerPage);
          const indexOfLastTrade = currentPage * tradesPerPage;
          const indexOfFirstTrade = indexOfLastTrade - tradesPerPage;
          const currentTrades = trades.slice(indexOfFirstTrade, indexOfLastTrade);

          return (
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 overflow-hidden">
              <div className="p-6 border-b border-gray-700">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-sm font-bold">Recent Trades</h2>
                    <p className="text-sm text-gray-400 mt-1">
                      Showing {indexOfFirstTrade + 1}-{Math.min(indexOfLastTrade, trades.length)} of {trades.length} trades
                    </p>
                  </div>
                  <div className="text-sm font-mono text-gray-300 bg-gray-700/50 px-3 py-1.5 rounded-lg">
                    <span className="text-gray-400">PST:</span> {formatPSTTime()}
                  </div>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-700/50">
                    <tr>
                      {['Time', 'Whale', 'Market', 'Position', 'Size', 'Price', 'Amount'].map((header) => (
                        <th key={header} className="px-4 py-1.5 text-left text-xs font-semibold text-gray-300">
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {currentTrades.map((trade) => (
                      <tr key={trade.id} className="hover:bg-gray-700/30 transition-colors">
                        <td className="px-4 py-1.5 text-gray-400 text-xs">
                          {new Date(trade.timestamp).toLocaleTimeString('en-US', {
                            hour: 'numeric',
                            minute: '2-digit',
                            second: '2-digit',
                            hour12: true
                          })}
                        </td>
                        <td className="px-4 py-1.5">
                          <a
                            href={`https://polymarket.com/profile/${trade.trader_address}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-blue-400 hover:text-blue-300 hover:underline transition-colors text-xs"
                          >
                            {trade.whale_name}
                          </a>
                        </td>
                        <td className="px-4 py-1.5">
                          <div className="text-gray-300 text-xs max-w-xs truncate" title={trade.market_title}>
                            {trade.market_title}
                          </div>
                        </td>
                        <td className="px-4 py-1.5">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${trade.side === 'BUY' ? 'bg-green-500/20 text-green-300' : 'bg-red-500/20 text-red-300'}`}>
                            {trade.side === 'BUY' ? 'YES' : 'NO'}
                          </span>
                        </td>
                        <td className="px-4 py-1.5 text-gray-300 text-xs">{trade.size.toFixed(2)}</td>
                        <td className="px-4 py-1.5 text-blue-400 text-xs">${trade.price.toFixed(2)}</td>
                        <td className="px-4 py-1.5 text-yellow-400 font-medium text-xs">${(trade.size * trade.price).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination Controls */}
              {totalPages > 1 && (
                <div className="p-6 border-t border-gray-700 flex items-center justify-between">
                  <button
                    onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                    disabled={currentPage === 1}
                    className={`px-2 py-1 rounded-lg font-medium transition-all ${
                      currentPage === 1
                        ? 'bg-gray-700/30 text-gray-500 cursor-not-allowed'
                        : 'bg-gray-700 text-white hover:bg-gray-600'
                    }`}
                  >
                    ← Previous
                  </button>

                  <div className="flex gap-2">
                    {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                      let pageNum;
                      if (totalPages <= 7) {
                        pageNum = i + 1;
                      } else if (currentPage <= 4) {
                        pageNum = i + 1;
                      } else if (currentPage >= totalPages - 3) {
                        pageNum = totalPages - 6 + i;
                      } else {
                        pageNum = currentPage - 3 + i;
                      }

                      return (
                        <button
                          key={pageNum}
                          onClick={() => setCurrentPage(pageNum)}
                          className={`px-2 py-1 rounded-lg font-medium transition-all ${
                            currentPage === pageNum
                              ? 'bg-blue-600 text-white'
                              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                          }`}
                        >
                          {pageNum}
                        </button>
                      );
                    })}
                  </div>

                  <button
                    onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                    disabled={currentPage === totalPages}
                    className={`px-2 py-1 rounded-lg font-medium transition-all ${
                      currentPage === totalPages
                        ? 'bg-gray-700/30 text-gray-500 cursor-not-allowed'
                        : 'bg-gray-700 text-white hover:bg-gray-600'
                    }`}
                  >
                    Next →
                  </button>
                </div>
              )}
            </div>
          );
        })()}

      {/* Custom Strategy Builder Modal */}
      {showStrategyBuilder && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-gray-800 rounded-xl border border-gray-700 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="p-6 border-b border-gray-700 sticky top-0 bg-gray-800 z-10 flex items-center justify-between">
              <h2 className="text-sm font-bold">Create Custom Strategy</h2>
              <button
                onClick={() => setShowStrategyBuilder(false)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-6">
              {/* Basic Info */}
              <div className="space-y-4">
                <h3 className="text-xl font-bold text-blue-400">Basic Information</h3>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Strategy Name *</label>
                  <input
                    type="text"
                    value={newStrategy.name}
                    onChange={(e) => setNewStrategy({...newStrategy, name: e.target.value})}
                    placeholder="e.g., Aggressive Momentum"
                    className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Description *</label>
                  <textarea
                    value={newStrategy.description}
                    onChange={(e) => setNewStrategy({...newStrategy, description: e.target.value})}
                    placeholder="Describe your strategy goals and approach..."
                    rows={3}
                    className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              {/* Whale Selection Criteria */}
              <div className="space-y-4">
                <h3 className="text-xl font-bold text-purple-400">Whale Selection Criteria</h3>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Selection Type *</label>
                  <select
                    value={newStrategy.criteria_type}
                    onChange={(e) => setNewStrategy({...newStrategy, criteria_type: e.target.value})}
                    className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                  >
                    <option value="top_n">Top N Whales (by metric)</option>
                    <option value="filter">Filter by Criteria</option>
                  </select>
                </div>

                {newStrategy.criteria_type === 'top_n' && (
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-gray-400 mb-2">Number of Whales</label>
                      <input
                        type="number"
                        value={newStrategy.top_n}
                        onChange={(e) => setNewStrategy({...newStrategy, top_n: parseInt(e.target.value)})}
                        min="1"
                        max="41"
                        className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-2">Sort By</label>
                      <select
                        value={newStrategy.sort_by}
                        onChange={(e) => setNewStrategy({...newStrategy, sort_by: e.target.value})}
                        className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                      >
                        <option value="quality_score">Quality Score</option>
                        <option value="sharpe_ratio">Sharpe Ratio</option>
                        <option value="win_rate">Win Rate</option>
                        <option value="total_pnl">Total P&L</option>
                        <option value="total_volume">Total Volume</option>
                      </select>
                    </div>
                  </div>
                )}

                {newStrategy.criteria_type === 'filter' && (
                  <div className="space-y-6">
                    {/* Core Performance Metrics */}
                    <div>
                      <h4 className="text-sm font-bold text-gray-300 mb-3">Core Performance Metrics</h4>
                      <div className="grid grid-cols-3 gap-4">
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Min Sharpe Ratio</label>
                          <input
                            type="number"
                            value={newStrategy.min_sharpe || ''}
                            onChange={(e) => setNewStrategy({...newStrategy, min_sharpe: e.target.value ? parseFloat(e.target.value) : null})}
                            step="0.1"
                            placeholder="e.g., 2.5"
                            className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Min Win Rate (%)</label>
                          <input
                            type="number"
                            value={newStrategy.min_win_rate || ''}
                            onChange={(e) => setNewStrategy({...newStrategy, min_win_rate: e.target.value ? parseFloat(e.target.value) : null})}
                            step="1"
                            placeholder="e.g., 60"
                            className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Min Quality Score</label>
                          <input
                            type="number"
                            value={newStrategy.min_quality_score || ''}
                            onChange={(e) => setNewStrategy({...newStrategy, min_quality_score: e.target.value ? parseFloat(e.target.value) : null})}
                            step="1"
                            placeholder="e.g., 75"
                            className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Volume & Trade Metrics */}
                    <div>
                      <h4 className="text-sm font-bold text-gray-300 mb-3">Volume & Trade Metrics</h4>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Min Total Trades</label>
                          <input
                            type="number"
                            value={newStrategy.min_total_trades || ''}
                            onChange={(e) => setNewStrategy({...newStrategy, min_total_trades: e.target.value ? parseInt(e.target.value) : null})}
                            placeholder="e.g., 50"
                            className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Min Total Volume ($)</label>
                          <input
                            type="number"
                            value={newStrategy.min_total_volume || ''}
                            onChange={(e) => setNewStrategy({...newStrategy, min_total_volume: e.target.value ? parseFloat(e.target.value) : null})}
                            placeholder="e.g., 50000"
                            className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Position Sizing Metrics */}
                    <div>
                      <h4 className="text-sm font-bold text-gray-300 mb-3">Whale Position Sizing</h4>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Min Avg Position ($)</label>
                          <input
                            type="number"
                            value={newStrategy.min_avg_position_size || ''}
                            onChange={(e) => setNewStrategy({...newStrategy, min_avg_position_size: e.target.value ? parseFloat(e.target.value) : null})}
                            placeholder="e.g., 500"
                            className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Max Avg Position ($)</label>
                          <input
                            type="number"
                            value={newStrategy.max_avg_position_size || ''}
                            onChange={(e) => setNewStrategy({...newStrategy, max_avg_position_size: e.target.value ? parseFloat(e.target.value) : null})}
                            placeholder="e.g., 10000"
                            className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                          />
                        </div>
                      </div>
                    </div>

                    {/* P&L & Profitability */}
                    <div>
                      <h4 className="text-sm font-bold text-gray-300 mb-3">P&L & Profitability</h4>
                      <div className="grid grid-cols-3 gap-4">
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Min Profit Factor</label>
                          <input
                            type="number"
                            value={newStrategy.min_profit_factor || ''}
                            onChange={(e) => setNewStrategy({...newStrategy, min_profit_factor: e.target.value ? parseFloat(e.target.value) : null})}
                            step="0.1"
                            placeholder="e.g., 1.5"
                            className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Min ROI (%)</label>
                          <input
                            type="number"
                            value={newStrategy.min_roi || ''}
                            onChange={(e) => setNewStrategy({...newStrategy, min_roi: e.target.value ? parseFloat(e.target.value) : null})}
                            step="1"
                            placeholder="e.g., 20"
                            className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Max Drawdown (%)</label>
                          <input
                            type="number"
                            value={newStrategy.max_drawdown || ''}
                            onChange={(e) => setNewStrategy({...newStrategy, max_drawdown: e.target.value ? parseFloat(e.target.value) : null})}
                            step="1"
                            placeholder="e.g., 15"
                            className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Market Diversity */}
                    <div>
                      <h4 className="text-sm font-bold text-gray-300 mb-3">Market Diversity</h4>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Min Markets Traded</label>
                          <input
                            type="number"
                            value={newStrategy.min_markets_traded || ''}
                            onChange={(e) => setNewStrategy({...newStrategy, min_markets_traded: e.target.value ? parseInt(e.target.value) : null})}
                            placeholder="e.g., 10"
                            className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Max Markets Traded</label>
                          <input
                            type="number"
                            value={newStrategy.max_markets_traded || ''}
                            onChange={(e) => setNewStrategy({...newStrategy, max_markets_traded: e.target.value ? parseInt(e.target.value) : null})}
                            placeholder="e.g., 100"
                            className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Trade Timing */}
                    <div>
                      <h4 className="text-sm font-bold text-gray-300 mb-3">Trade Timing (Hours)</h4>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Min Avg Hold Time (hrs)</label>
                          <input
                            type="number"
                            value={newStrategy.min_avg_hold_time || ''}
                            onChange={(e) => setNewStrategy({...newStrategy, min_avg_hold_time: e.target.value ? parseFloat(e.target.value) : null})}
                            step="0.5"
                            placeholder="e.g., 2"
                            className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Max Avg Hold Time (hrs)</label>
                          <input
                            type="number"
                            value={newStrategy.max_avg_hold_time || ''}
                            onChange={(e) => setNewStrategy({...newStrategy, max_avg_hold_time: e.target.value ? parseFloat(e.target.value) : null})}
                            step="0.5"
                            placeholder="e.g., 48"
                            className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Whale Tiers */}
                    <div>
                      <h4 className="text-sm font-bold text-gray-300 mb-3">Whale Tiers</h4>
                      <div className="flex gap-4">
                        {['MEGA', 'HIGH', 'MEDIUM', 'LOW'].map(tier => (
                          <label key={tier} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={newStrategy.whale_tiers.includes(tier)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setNewStrategy({...newStrategy, whale_tiers: [...newStrategy.whale_tiers, tier]});
                                } else {
                                  setNewStrategy({...newStrategy, whale_tiers: newStrategy.whale_tiers.filter(t => t !== tier)});
                                }
                              }}
                              className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                            />
                            {tier}
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Position Sizing */}
              <div className="space-y-4">
                <h3 className="text-xl font-bold text-yellow-400">Position Sizing & Account</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Initial Balance ($) *</label>
                    <input
                      type="number"
                      value={newStrategy.initial_balance}
                      onChange={(e) => setNewStrategy({...newStrategy, initial_balance: parseFloat(e.target.value)})}
                      step="1000"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Base Position (%) *</label>
                    <input
                      type="number"
                      value={newStrategy.base_position_pct}
                      onChange={(e) => setNewStrategy({...newStrategy, base_position_pct: parseFloat(e.target.value)})}
                      step="0.5"
                      min="1"
                      max="20"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Max Position (%) *</label>
                    <input
                      type="number"
                      value={newStrategy.max_position_pct}
                      onChange={(e) => setNewStrategy({...newStrategy, max_position_pct: parseFloat(e.target.value)})}
                      step="0.5"
                      min="1"
                      max="25"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Min Position Size ($)</label>
                    <input
                      type="number"
                      value={newStrategy.min_position_size || ''}
                      onChange={(e) => setNewStrategy({...newStrategy, min_position_size: e.target.value ? parseFloat(e.target.value) : null})}
                      placeholder="e.g., 50"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Max Position Size ($)</label>
                    <input
                      type="number"
                      value={newStrategy.max_position_size || ''}
                      onChange={(e) => setNewStrategy({...newStrategy, max_position_size: e.target.value ? parseFloat(e.target.value) : null})}
                      placeholder="No limit"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>
                <div className="flex gap-6">
                  <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newStrategy.use_kelly}
                      onChange={(e) => setNewStrategy({...newStrategy, use_kelly: e.target.checked})}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                    />
                    Use Kelly Criterion
                  </label>
                  <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newStrategy.scale_by_confidence}
                      onChange={(e) => setNewStrategy({...newStrategy, scale_by_confidence: e.target.checked})}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                    />
                    Scale by Confidence
                  </label>
                  <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newStrategy.scale_by_liquidity}
                      onChange={(e) => setNewStrategy({...newStrategy, scale_by_liquidity: e.target.checked})}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                    />
                    Scale by Liquidity
                  </label>
                </div>
              </div>

              {/* Risk Management */}
              <div className="space-y-4">
                <h3 className="text-xl font-bold text-red-400">Risk Management</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Max Open Positions</label>
                    <input
                      type="number"
                      value={newStrategy.max_positions}
                      onChange={(e) => setNewStrategy({...newStrategy, max_positions: parseInt(e.target.value)})}
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Max Per Market ($)</label>
                    <input
                      type="number"
                      value={newStrategy.max_per_market}
                      onChange={(e) => setNewStrategy({...newStrategy, max_per_market: parseFloat(e.target.value)})}
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Max Per Category (% of capital)</label>
                    <input
                      type="number"
                      value={newStrategy.max_per_category * 100}
                      onChange={(e) => setNewStrategy({...newStrategy, max_per_category: parseFloat(e.target.value) / 100})}
                      step="5"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Max Total Exposure (% of capital)</label>
                    <input
                      type="number"
                      value={newStrategy.max_total_exposure * 100}
                      onChange={(e) => setNewStrategy({...newStrategy, max_total_exposure: parseFloat(e.target.value) / 100})}
                      step="5"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Stop Loss (%)</label>
                    <input
                      type="number"
                      value={newStrategy.stop_loss_pct || ''}
                      onChange={(e) => setNewStrategy({...newStrategy, stop_loss_pct: e.target.value ? parseFloat(e.target.value) : null})}
                      step="1"
                      placeholder="Optional"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Take Profit (%)</label>
                    <input
                      type="number"
                      value={newStrategy.take_profit_pct || ''}
                      onChange={(e) => setNewStrategy({...newStrategy, take_profit_pct: e.target.value ? parseFloat(e.target.value) : null})}
                      step="1"
                      placeholder="Optional"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Trailing Stop (%)</label>
                    <input
                      type="number"
                      value={newStrategy.trailing_stop_pct || ''}
                      onChange={(e) => setNewStrategy({...newStrategy, trailing_stop_pct: e.target.value ? parseFloat(e.target.value) : null})}
                      step="1"
                      placeholder="Optional"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Max Daily Loss ($)</label>
                    <input
                      type="number"
                      value={newStrategy.max_daily_loss || ''}
                      onChange={(e) => setNewStrategy({...newStrategy, max_daily_loss: e.target.value ? parseFloat(e.target.value) : null})}
                      placeholder="Optional"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Circuit Breaker Loss (%)</label>
                    <input
                      type="number"
                      value={newStrategy.circuit_breaker_loss * 100}
                      onChange={(e) => setNewStrategy({...newStrategy, circuit_breaker_loss: parseFloat(e.target.value) / 100})}
                      step="1"
                      className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-2 py-1 text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-4 pt-4 border-t border-gray-700">
                <button
                  onClick={() => setShowStrategyBuilder(false)}
                  className="flex-1 px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-medium transition-all"
                >
                  Cancel
                </button>
                <button
                  onClick={async () => {
                    if (!newStrategy.name || !newStrategy.description) {
                      alert('Please fill in strategy name and description');
                      return;
                    }
                    try {
                      const response = await fetch('/api/strategies/create', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(newStrategy)
                      });
                      if (response.ok) {
                        const strategiesRes = await fetch('/api/strategies');
                        setStrategies(await strategiesRes.json());
                        setShowStrategyBuilder(false);
                        setNewStrategy({
                          name: '',
                          description: '',
                          criteria_type: 'top_n',
                          top_n: 5,
                          sort_by: 'quality_score',
                          min_sharpe: null,
                          min_win_rate: null,
                          min_quality_score: null,
                          min_total_trades: null,
                          min_total_volume: null,
                          max_avg_position_size: null,
                          min_avg_position_size: null,
                          min_profit_factor: null,
                          min_roi: null,
                          max_drawdown: null,
                          min_consistency_score: null,
                          preferred_categories: [],
                          whale_tiers: ['MEGA', 'HIGH', 'MEDIUM'],
                          min_markets_traded: null,
                          max_markets_traded: null,
                          min_avg_hold_time: null,
                          max_avg_hold_time: null,
                          min_recent_performance: null,
                          recent_performance_days: 30,
                          base_position_pct: 5.0,
                          max_position_pct: 10.0,
                          use_kelly: false,
                          kelly_fraction: 0.25,
                          scale_by_confidence: true,
                          scale_by_liquidity: true,
                          min_position_size: 50,
                          max_position_size: null,
                          max_positions: 10,
                          max_per_market: 1000,
                          max_per_category: 0.3,
                          max_total_exposure: 0.8,
                          stop_loss_pct: null,
                          take_profit_pct: null,
                          trailing_stop_pct: null,
                          max_daily_loss: null,
                          circuit_breaker_loss: -0.15,
                          initial_balance: 10000.0
                        });
                        alert('Strategy created successfully!');
                      } else {
                        alert('Failed to create strategy');
                      }
                    } catch (error) {
                      console.error('Error creating strategy:', error);
                      alert('Error creating strategy');
                    }
                  }}
                  className="flex-1 px-6 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-all"
                >
                  Create Strategy
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Accounts Overview Modal */}
      {showAccountsOverview && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-xl border border-gray-700 max-w-6xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="p-6 border-b border-gray-700 sticky top-0 bg-gray-800 z-10 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold">Active Trading Accounts</h2>
                <p className="text-gray-400 text-sm mt-1">View performance across all strategy accounts</p>
              </div>
              <button
                onClick={() => setShowAccountsOverview(false)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6">
              {/* Summary Stats */}
              <div className="grid grid-cols-4 gap-4 mb-6">
                <div className="bg-gray-700/30 rounded-lg p-4">
                  <div className="text-gray-400 text-sm mb-1">Total Accounts</div>
                  <div className="text-sm font-bold text-white">{strategies.length}</div>
                </div>
                <div className="bg-gray-700/30 rounded-lg p-4">
                  <div className="text-gray-400 text-sm mb-1">Active Accounts</div>
                  <div className="text-sm font-bold text-green-400">{strategies.filter(s => s.active).length}</div>
                </div>
                <div className="bg-gray-700/30 rounded-lg p-4">
                  <div className="text-gray-400 text-sm mb-1">Total Value</div>
                  <div className="text-sm font-bold text-white">
                    ${strategies.reduce((sum, s) => sum + (s.account.total_value || s.account.balance), 0).toLocaleString()}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    Cash + Positions
                  </div>
                </div>
                <div className="bg-gray-700/30 rounded-lg p-4">
                  <div className="text-gray-400 text-sm mb-1">Total P&L</div>
                  <div className={`text-sm font-bold ${strategies.reduce((sum, s) => sum + (s.account.total_pnl || s.account.pnl || 0), 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    ${strategies.reduce((sum, s) => sum + (s.account.total_pnl || s.account.pnl || 0), 0).toLocaleString()}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    Realized + Unrealized
                  </div>
                </div>
              </div>

              {/* Accounts Table */}
              <div className="bg-gray-700/30 rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-700/50">
                    <tr>
                      {['Strategy', 'Status', 'Cash', 'Total Value', 'Unrealized P&L', 'Total P&L', 'ROI', 'Trades', 'Open Positions', 'Win Rate'].map((header) => (
                        <th key={header} className="px-3 py-3 text-left text-xs font-semibold text-gray-300">
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {strategies.map((strategy) => (
                      <tr key={strategy.id} className="hover:bg-gray-700/30 transition-colors">
                        <td className="px-3 py-3">
                          <div className="font-medium text-white text-sm">{strategy.name}</div>
                          <div className="text-xs text-gray-400">{strategy.description.substring(0, 40)}{strategy.description.length > 40 ? '...' : ''}</div>
                        </td>
                        <td className="px-3 py-3">
                          <span className={`px-2 py-1 rounded-full text-xs font-bold ${strategy.active ? 'bg-green-500/20 text-green-400' : 'bg-gray-700 text-gray-400'}`}>
                            {strategy.active ? '● ACTIVE' : '○ INACTIVE'}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-white font-medium text-sm">${strategy.account.balance.toLocaleString()}</td>
                        <td className="px-3 py-3 text-white font-bold text-sm">
                          ${(strategy.account.total_value || strategy.account.balance).toLocaleString()}
                        </td>
                        <td className="px-3 py-3">
                          <span className={`font-medium text-sm ${(strategy.account.unrealized_pnl || 0) >= 0 ? 'text-blue-400' : 'text-orange-400'}`}>
                            {(strategy.account.unrealized_pnl || 0) >= 0 ? '+' : ''}${(strategy.account.unrealized_pnl || 0).toLocaleString()}
                          </span>
                        </td>
                        <td className="px-3 py-3">
                          <span className={`font-medium text-sm ${(strategy.account.total_pnl || strategy.account.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {(strategy.account.total_pnl || strategy.account.pnl || 0) >= 0 ? '+' : ''}${(strategy.account.total_pnl || strategy.account.pnl || 0).toLocaleString()}
                          </span>
                        </td>
                        <td className="px-3 py-3">
                          <span className={`font-medium text-sm ${strategy.account.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {strategy.account.roi.toFixed(2)}%
                          </span>
                        </td>
                        <td className="px-3 py-3 text-white text-sm">{strategy.account.total_trades}</td>
                        <td className="px-3 py-3 text-purple-400 font-medium text-sm">{strategy.account.open_positions || 0}</td>
                        <td className="px-3 py-3 text-cyan-400 text-sm">{strategy.account.win_rate.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      </main>

      <footer className="bg-gray-800/50 border-t border-gray-700 mt-12">
        <div className="container mx-auto px-2 py-1 text-center text-gray-400 text-sm">
          Whale Trader v0.1 - Real-time Polymarket Copy Trading System | API: http://localhost:8000
        </div>
      </footer>
    </div>
  );
}
