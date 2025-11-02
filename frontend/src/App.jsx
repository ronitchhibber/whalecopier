import { useState, useEffect } from 'react';

export default function App() {
  const [stats, setStats] = useState(null);
  const [whales, setWhales] = useState([]);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [tradesFilter, setTradesFilter] = useState('all'); // all, buys, sells
  const [paperTradingEnabled, setPaperTradingEnabled] = useState(false);
  const [selectedMarket, setSelectedMarket] = useState(null);
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [agentsError, setAgentsError] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [tradesPerPage] = useState(20);
  const [whalesPage, setWhalesPage] = useState(1);
  const [whalesPerPage] = useState(25);
  const [strategies, setStrategies] = useState([]);
  const [strategiesLoading, setStrategiesLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, whalesRes, tradesRes, strategiesRes] = await Promise.all([
          fetch('/api/stats/summary'),
          fetch('/api/whales?limit=20'),
          fetch('/api/trades?limit=1000'),
          fetch('/api/strategies')
        ]);
        setStats(await statsRes.json());
        setWhales(await whalesRes.json());
        setTrades(await tradesRes.json());
        setStrategies(await strategiesRes.json());
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

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        setAgentsLoading(true);
        setAgentsError(null);
        const res = await fetch('/api/agents');
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        const data = await res.json();
        console.log('Agents loaded:', data.agents);
        setAgents(data.agents || []);
      } catch (error) {
        console.error('Error fetching agents:', error);
        setAgentsError(error.message);
      } finally {
        setAgentsLoading(false);
      }
    };
    fetchAgents();
  }, []);

  if (loading) return <div className="flex items-center justify-center min-h-screen">Loading...</div>;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      <nav className="bg-gray-800/50 border-b border-gray-700 backdrop-blur-lg">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
              Whale Trader v0.1
            </h1>
            <div className="flex gap-4">
              {['dashboard', 'trades', 'strategies', 'trading', 'agents'].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 rounded-lg font-medium transition-all ${activeTab === tab ? 'bg-blue-600 text-white' : 'bg-gray-700/50 text-gray-300 hover:bg-gray-700'}`}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>
      </nav>

      <main className="container mx-auto px-6 py-8">
        {activeTab === 'dashboard' && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
              {[
                { label: 'Total Whales', value: stats?.total_whales, color: 'blue' },
                { label: '24h Trades', value: stats?.trades_24h, color: 'green' },
                { label: '24h Volume', value: `$${stats?.volume_24h?.toLocaleString()}`, color: 'purple' },
                { label: 'Paper Balance', value: `$${stats?.paper_balance?.toLocaleString()}`, color: 'yellow' },
                { label: 'Paper P&L', value: `$${stats?.paper_pnl?.toLocaleString()}`, color: stats?.paper_pnl >= 0 ? 'green' : 'red' },
              ].map((stat) => (
                <div key={stat.label} className="bg-gray-800/50 backdrop-blur-lg rounded-xl p-6 border border-gray-700">
                  <div className="text-gray-400 text-sm mb-2">{stat.label}</div>
                  <div className={`text-3xl font-bold text-${stat.color}-400`}>{stat.value}</div>
                </div>
              ))}
            </div>

            {/* Active Whales with Pagination */}
            {(() => {
              const totalWhalesPages = Math.ceil(whales.length / whalesPerPage);
              const indexOfLastWhale = whalesPage * whalesPerPage;
              const indexOfFirstWhale = indexOfLastWhale - whalesPerPage;
              const currentWhales = whales.slice(indexOfFirstWhale, indexOfLastWhale);

              return (
                <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 overflow-hidden">
                  <div className="p-6 border-b border-gray-700">
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="text-2xl font-bold">Active Whales</h2>
                        <p className="text-sm text-gray-400 mt-1">
                          Showing {indexOfFirstWhale + 1}-{Math.min(indexOfLastWhale, whales.length)} of {whales.length} qualified whales
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-gray-700/50">
                        <tr>
                          {['Whale', 'Tier', 'Win Rate', 'Sharpe', 'Total P&L', 'Volume', 'Trades', '24h Trades'].map((header) => (
                            <th key={header} className="px-6 py-4 text-left text-sm font-semibold text-gray-300">
                              {header}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-700">
                        {currentWhales.map((whale) => (
                          <tr key={whale.address} className="hover:bg-gray-700/30 transition-colors">
                            <td className="px-6 py-4">
                              <div>
                                <div className="font-medium text-white">{whale.pseudonym}</div>
                                <div className="text-xs text-gray-400">{whale.address.slice(0, 10)}...</div>
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <span className={`px-3 py-1 rounded-full text-xs font-bold ${whale.tier === 'MEGA' ? 'bg-purple-500/20 text-purple-300' : whale.tier === 'HIGH' ? 'bg-blue-500/20 text-blue-300' : 'bg-green-500/20 text-green-300'}`}>
                                {whale.tier}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-green-400 font-medium">{whale.win_rate}%</td>
                            <td className="px-6 py-4 text-blue-400 font-medium">{whale.sharpe_ratio}</td>
                            <td className="px-6 py-4 text-yellow-400 font-bold">${whale.total_pnl.toLocaleString()}</td>
                            <td className="px-6 py-4 text-gray-300">${whale.total_volume.toLocaleString()}</td>
                            <td className="px-6 py-4 text-gray-300">{whale.total_trades}</td>
                            <td className="px-6 py-4">
                              <span className="text-cyan-400 font-medium">{whale.trades_24h || 0}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination Controls */}
                  {totalWhalesPages > 1 && (
                    <div className="p-6 border-t border-gray-700 flex items-center justify-between">
                      <button
                        onClick={() => setWhalesPage(prev => Math.max(prev - 1, 1))}
                        disabled={whalesPage === 1}
                        className={`px-4 py-2 rounded-lg font-medium transition-all ${
                          whalesPage === 1
                            ? 'bg-gray-700/30 text-gray-500 cursor-not-allowed'
                            : 'bg-gray-700 text-white hover:bg-gray-600'
                        }`}
                      >
                        ← Previous
                      </button>

                      <div className="flex gap-2">
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
                              className={`px-4 py-2 rounded-lg font-medium transition-all ${
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
                        className={`px-4 py-2 rounded-lg font-medium transition-all ${
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
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Paper Trading Control */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-bold mb-2">Paper Trading</h2>
                  <p className="text-gray-400">Start paper trading with virtual funds to test strategies</p>
                </div>
                <button
                  onClick={() => setPaperTradingEnabled(!paperTradingEnabled)}
                  className={`px-6 py-3 rounded-lg font-bold transition-all ${
                    paperTradingEnabled
                      ? 'bg-red-600 hover:bg-red-700 text-white'
                      : 'bg-green-600 hover:bg-green-700 text-white'
                  }`}
                >
                  {paperTradingEnabled ? '🛑 Stop Paper Trading' : '▶️ Start Paper Trading'}
                </button>
              </div>

              {paperTradingEnabled && (
                <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
                  <div className="flex items-center gap-3">
                    <div className="h-3 w-3 rounded-full bg-green-500 animate-pulse"></div>
                    <span className="text-green-400 font-medium">Paper trading is ACTIVE</span>
                  </div>
                  <p className="text-gray-400 text-sm mt-2">
                    Copying trades from top whales with virtual $100,000 balance
                  </p>
                </div>
              )}
            </div>

            {/* Trading Configuration */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-6">
              <h3 className="text-xl font-bold mb-4">Configuration</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Initial Balance</label>
                  <input
                    type="number"
                    defaultValue="100000"
                    className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-4 py-2 text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Max Position Size (%)</label>
                  <input
                    type="number"
                    defaultValue="5"
                    className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-4 py-2 text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Stop Loss (%)</label>
                  <input
                    type="number"
                    defaultValue="10"
                    className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-4 py-2 text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Take Profit (%)</label>
                  <input
                    type="number"
                    defaultValue="20"
                    className="w-full bg-gray-700/50 border border-gray-600 rounded-lg px-4 py-2 text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>
            </div>

            {/* Active Positions */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700">
              <div className="p-6 border-b border-gray-700">
                <h3 className="text-xl font-bold">Active Positions</h3>
              </div>
              <div className="p-6">
                {paperTradingEnabled ? (
                  <div className="text-center text-gray-400 py-8">
                    <p className="text-lg mb-2">Monitoring for whale trades...</p>
                    <p className="text-sm">Positions will appear here when whales make trades</p>
                  </div>
                ) : (
                  <div className="text-center text-gray-400 py-8">
                    <p className="text-lg mb-2">Paper trading is stopped</p>
                    <p className="text-sm">Click "Start Paper Trading" to begin</p>
                  </div>
                )}
              </div>
            </div>

            {/* Performance Stats */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-6">
              <h3 className="text-xl font-bold mb-4">Performance Stats</h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-gray-700/30 rounded-lg p-4">
                  <div className="text-gray-400 text-sm mb-1">Total Trades</div>
                  <div className="text-2xl font-bold text-white">0</div>
                </div>
                <div className="bg-gray-700/30 rounded-lg p-4">
                  <div className="text-gray-400 text-sm mb-1">Win Rate</div>
                  <div className="text-2xl font-bold text-green-400">0%</div>
                </div>
                <div className="bg-gray-700/30 rounded-lg p-4">
                  <div className="text-gray-400 text-sm mb-1">Total P&L</div>
                  <div className="text-2xl font-bold text-yellow-400">$0</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'strategies' && (
          <div className="space-y-6">
            {/* Header */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-6">
              <h2 className="text-3xl font-bold mb-2">Trading Strategies</h2>
              <p className="text-gray-400">Activate strategies to test different whale copy-trading approaches. Each strategy has its own virtual $10,000 paper trading account.</p>
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
                            <div className={`text-lg font-bold ${strategy.account.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              ${strategy.account.pnl.toLocaleString()}
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
                            className={`flex-1 px-4 py-2 rounded-lg font-medium transition-all ${
                              strategy.active
                                ? 'bg-red-600 hover:bg-red-700 text-white'
                                : 'bg-green-600 hover:bg-green-700 text-white'
                            }`}
                          >
                            {strategy.active ? '⏸ Deactivate' : '▶ Activate'}
                          </button>
                          <button
                            onClick={handleReset}
                            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg font-medium transition-all"
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
          const filteredTrades = trades.filter(trade => {
            if (tradesFilter === 'buys') return trade.side === 'BUY';
            if (tradesFilter === 'sells') return trade.side === 'SELL';
            return true;
          });

          const totalPages = Math.ceil(filteredTrades.length / tradesPerPage);
          const indexOfLastTrade = currentPage * tradesPerPage;
          const indexOfFirstTrade = indexOfLastTrade - tradesPerPage;
          const currentTrades = filteredTrades.slice(indexOfFirstTrade, indexOfLastTrade);

          return (
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 overflow-hidden">
              <div className="p-6 border-b border-gray-700">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-2xl font-bold">Recent Trades</h2>
                    <p className="text-sm text-gray-400 mt-1">
                      Showing {indexOfFirstTrade + 1}-{Math.min(indexOfLastTrade, filteredTrades.length)} of {filteredTrades.length} trades
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {['all', 'buys', 'sells'].map((filter) => (
                      <button
                        key={filter}
                        onClick={() => {
                          setTradesFilter(filter);
                          setCurrentPage(1);
                        }}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                          tradesFilter === filter
                            ? filter === 'buys'
                              ? 'bg-green-600 text-white'
                              : filter === 'sells'
                              ? 'bg-red-600 text-white'
                              : 'bg-blue-600 text-white'
                            : 'bg-gray-700/50 text-gray-300 hover:bg-gray-700'
                        }`}
                      >
                        {filter === 'all' ? 'All Trades' : filter === 'buys' ? 'Buys Only' : 'Sells Only'}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-700/50">
                    <tr>
                      {['Time', 'Whale', 'Market', 'Side', 'Size', 'Price', 'Amount'].map((header) => (
                        <th key={header} className="px-6 py-4 text-left text-sm font-semibold text-gray-300">
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {currentTrades.map((trade) => (
                      <tr key={trade.id} className="hover:bg-gray-700/30 transition-colors">
                        <td className="px-6 py-4 text-gray-400 text-sm">
                          {new Date(trade.timestamp).toLocaleTimeString('en-US', {
                            hour: 'numeric',
                            minute: '2-digit',
                            hour12: true,
                            timeZone: 'America/Los_Angeles'
                          })} PST
                        </td>
                        <td className="px-6 py-4">
                          <a
                            href={`https://polymarket.com/profile/${trade.trader_address}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-blue-400 hover:text-blue-300 hover:underline transition-colors"
                          >
                            {trade.whale_name}
                          </a>
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-gray-300 text-sm max-w-xs truncate" title={trade.market_title}>
                            {trade.market_title}
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-xs font-bold ${trade.side === 'BUY' ? 'bg-green-500/20 text-green-300' : 'bg-red-500/20 text-red-300'}`}>
                            {trade.side}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-gray-300">{trade.size.toFixed(2)}</td>
                        <td className="px-6 py-4 text-blue-400">${trade.price.toFixed(2)}</td>
                        <td className="px-6 py-4 text-yellow-400 font-medium">${trade.amount.toFixed(2)}</td>
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
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${
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
                          className={`px-4 py-2 rounded-lg font-medium transition-all ${
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
                    className={`px-4 py-2 rounded-lg font-medium transition-all ${
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

        {activeTab === 'agents' && (
          <div className="space-y-6">
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-6">
              <h2 className="text-2xl font-bold mb-2">AI Agents Dashboard</h2>
              <p className="text-gray-400">
                Monitor and control the 6-agent system powering intelligent whale copy-trading
              </p>
            </div>

            {agentsLoading ? (
              <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-12 text-center">
                <div className="text-gray-400 text-lg mb-2">Loading agents...</div>
                <div className="text-gray-500 text-sm">Fetching agent information from API</div>
              </div>
            ) : agentsError ? (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6">
                <div className="text-red-400 font-bold mb-2">Error Loading Agents</div>
                <div className="text-gray-400">{agentsError}</div>
                <button
                  onClick={() => window.location.reload()}
                  className="mt-4 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
                >
                  Retry
                </button>
              </div>
            ) : agents.length === 0 ? (
              <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-12 text-center">
                <div className="text-gray-400 text-lg mb-2">No agents found</div>
                <div className="text-gray-500 text-sm">Check that the API is running on port 8000</div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {agents.map((agent) => {
                  return (
                    <div
                      key={agent.id}
                      className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 p-6 hover:border-blue-500/50 transition-all cursor-pointer"
                      onClick={() => setSelectedAgent(agent)}
                    >
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <h3 className="text-lg font-bold text-white mb-1">{agent.name}</h3>
                          <p className="text-sm text-gray-400">{agent.description}</p>
                        </div>
                        <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                          agent.status === 'active'
                            ? 'bg-green-500/20 text-green-300'
                            : 'bg-gray-500/20 text-gray-300'
                        }`}>
                          {agent.status}
                        </span>
                      </div>

                      <div className="space-y-2">
                        <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Capabilities</div>
                        {agent.capabilities.slice(0, 3).map((capability, idx) => (
                          <div key={idx} className="flex items-center gap-2 text-sm text-gray-300">
                            <div className="h-1.5 w-1.5 rounded-full bg-blue-400"></div>
                            {capability.replace(/_/g, ' ')}
                          </div>
                        ))}
                      </div>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedAgent(agent);
                        }}
                        className="mt-4 w-full bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                      >
                        View Details
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {selectedAgent && (
              <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                <div className="bg-gray-800 rounded-xl border border-gray-700 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
                  <div className="p-6 border-b border-gray-700 flex items-center justify-between sticky top-0 bg-gray-800 z-10">
                    <h3 className="text-2xl font-bold">{selectedAgent.name}</h3>
                    <button
                      onClick={() => setSelectedAgent(null)}
                      className="text-gray-400 hover:text-white transition-colors"
                    >
                      ✕
                    </button>
                  </div>

                  <div className="p-6 space-y-6">
                    <div>
                      <div className="text-sm text-gray-400 mb-2">Description</div>
                      <p className="text-gray-300">{selectedAgent.description}</p>
                    </div>

                    <div>
                      <div className="text-sm text-gray-400 mb-2">Status</div>
                      <span className={`px-3 py-1 rounded-full text-sm font-bold ${
                        selectedAgent.status === 'active'
                          ? 'bg-green-500/20 text-green-300'
                          : 'bg-gray-500/20 text-gray-300'
                      }`}>
                        {selectedAgent.status.toUpperCase()}
                      </span>
                    </div>

                    <div>
                      <div className="text-sm text-gray-400 mb-3">Capabilities</div>
                      <div className="space-y-2">
                        {selectedAgent.capabilities.map((capability, idx) => (
                          <div key={idx} className="bg-gray-700/30 rounded-lg p-3 flex items-center gap-3">
                            <div className="h-2 w-2 rounded-full bg-blue-400"></div>
                            <span className="text-gray-300">{capability.replace(/_/g, ' ')}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="flex gap-3">
                      <button
                        onClick={() => {
                          fetch(`/api/agents/${selectedAgent.id}/execute`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ task: 'default' })
                          });
                          alert(`Task submitted to ${selectedAgent.name}`);
                        }}
                        className="flex-1 bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-medium transition-colors"
                      >
                        Execute Task
                      </button>
                      <button
                        onClick={() => setSelectedAgent(null)}
                        className="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-medium transition-colors"
                      >
                        Close
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      <footer className="bg-gray-800/50 border-t border-gray-700 mt-12">
        <div className="container mx-auto px-6 py-4 text-center text-gray-400 text-sm">
          Whale Trader v0.1 - Real-time Polymarket Copy Trading System | API: http://localhost:8000
        </div>
      </footer>
    </div>
  );
}
