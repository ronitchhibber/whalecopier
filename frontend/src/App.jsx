import { useState, useEffect } from 'react';

export default function App() {
  const [stats, setStats] = useState(null);
  const [whales, setWhales] = useState([]);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [paperTradingEnabled, setPaperTradingEnabled] = useState(false);
  const [selectedMarket, setSelectedMarket] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, whalesRes, tradesRes] = await Promise.all([
          fetch('/api/stats/summary'),
          fetch('/api/whales?limit=20'),
          fetch('/api/trades?limit=10')
        ]);
        setStats(await statsRes.json());
        setWhales(await whalesRes.json());
        setTrades(await tradesRes.json());
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
              {['dashboard', 'trades', 'trading'].map((tab) => (
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

            {/* Top Whales under Dashboard */}
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 overflow-hidden">
              <div className="p-6 border-b border-gray-700">
                <h2 className="text-2xl font-bold">Top Whales</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-700/50">
                    <tr>
                      {['Whale', 'Tier', 'Win Rate', 'Sharpe', 'Total P&L', 'Volume', 'Trades'].map((header) => (
                        <th key={header} className="px-6 py-4 text-left text-sm font-semibold text-gray-300">
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {whales.slice(0, 10).map((whale) => (
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
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
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

        {activeTab === 'trades' && (
          <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 overflow-hidden">
            <div className="p-6 border-b border-gray-700">
              <h2 className="text-2xl font-bold">Recent Trades</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-700/50">
                  <tr>
                    {['Time', 'Whale', 'Side', 'Size', 'Price', 'Amount'].map((header) => (
                      <th key={header} className="px-6 py-4 text-left text-sm font-semibold text-gray-300">
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {trades.map((trade) => (
                    <tr key={trade.id} className="hover:bg-gray-700/30 transition-colors">
                      <td className="px-6 py-4 text-gray-400 text-sm">{new Date(trade.timestamp).toLocaleString()}</td>
                      <td className="px-6 py-4">
                        <div className="font-medium text-white">{trade.whale_name}</div>
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
