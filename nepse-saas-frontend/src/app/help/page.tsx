'use client';

import { useState } from 'react';
import { 
  HelpCircle,
  Search,
  TrendingUp,
  BarChart3,
  Calendar,
  Coins,
  Activity,
  AlertTriangle,
  ChevronRight,
  BookOpen,
  Settings,
  Zap,
  Shield,
  Target,
  Crosshair,
} from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';

// Feature card
function FeatureCard({ 
  title, 
  description,
  icon: Icon,
  href,
  tags,
}: { 
  title: string;
  description: string;
  icon: React.ElementType;
  href: string;
  tags: string[];
}) {
  return (
    <Link 
      href={href}
      className="block rounded-xl border border-border bg-card p-5 transition-all hover:shadow-card-hover hover:border-primary/30"
    >
      <div className="flex items-start gap-4">
        <div className="p-2.5 rounded-lg bg-primary/10">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold mb-1">{title}</h3>
          <p className="text-sm text-muted-foreground mb-3">{description}</p>
          <div className="flex flex-wrap gap-2">
            {tags.map(tag => (
              <span key={tag} className="px-2 py-0.5 bg-muted/20 rounded text-xs text-muted-foreground">
                {tag}
              </span>
            ))}
          </div>
        </div>
        <ChevronRight className="h-5 w-5 text-muted-foreground" />
      </div>
    </Link>
  );
}

// Quick tip
function QuickTip({ title, content }: { title: string; content: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="font-medium text-sm mb-1">{title}</p>
      <p className="text-sm text-muted-foreground">{content}</p>
    </div>
  );
}

const features = [
  {
    title: 'Trading Signal Generator',
    description: 'Get AI-powered BUY/SELL/HOLD signals with entry prices, targets, and stop losses.',
    icon: Zap,
    href: '/signal',
    tags: ['Entry', 'Target', 'Stop Loss', 'Confidence'],
  },
  {
    title: 'Stock Analyzer',
    description: 'Deep technical analysis with EMAs, RSI, MACD, support/resistance, and trend phases.',
    icon: TrendingUp,
    href: '/analyze',
    tags: ['Technical', 'Trend', 'Support', 'Resistance'],
  },
  {
    title: 'Position Advisor',
    description: 'Should you hold or sell? Enter your buy price for personalized advice.',
    icon: Shield,
    href: '/hold-or-sell',
    tags: ['Hold', 'Sell', 'P/L', 'Risk'],
  },
  {
    title: 'IPO Exit Timing',
    description: 'When to sell newly listed IPO stocks based on volume and broker flow patterns.',
    icon: AlertTriangle,
    href: '/ipo-exit',
    tags: ['IPO', 'Volume', 'Distribution', 'Exit'],
  },
  {
    title: 'Trading Calendar',
    description: 'Upcoming signals and events for the week with sector rotation.',
    icon: Calendar,
    href: '/calendar',
    tags: ['Schedule', 'Sector', 'Weekly'],
  },
  {
    title: 'Smart Money Tracker',
    description: 'Track institutional and smart money flow through broker activity.',
    icon: Crosshair,
    href: '/smart-money',
    tags: ['Brokers', 'Accumulation', 'Distribution'],
  },
  {
    title: 'Market Heatmap',
    description: 'Visualize market performance by sector and individual stocks.',
    icon: BarChart3,
    href: '/heatmap',
    tags: ['Sectors', 'Gainers', 'Losers'],
  },
  {
    title: 'Sector Rotation',
    description: 'Weekly sector momentum ranking to catch rotations early.',
    icon: Activity,
    href: '/sector-rotation',
    tags: ['Momentum', 'Rotation', 'Ranking'],
  },
  {
    title: 'Dividend Forecast',
    description: 'EPS-based dividend predictions and yield analysis.',
    icon: Coins,
    href: '/dividend',
    tags: ['Dividend', 'Yield', 'Forecast'],
  },
  {
    title: 'Price Targets',
    description: 'Fibonacci, ATR, and volume profile based price targets.',
    icon: Target,
    href: '/price-targets',
    tags: ['Fibonacci', 'ATR', 'Targets'],
  },
];

const tips = [
  {
    title: 'Start with Signal Generator',
    content: 'Enter any stock symbol to get an instant BUY/SELL/HOLD recommendation with confidence level.',
  },
  {
    title: 'Use Position Advisor for Holdings',
    content: 'If you already own a stock, use Hold or Sell to get personalized advice based on your entry price.',
  },
  {
    title: 'Check Calendar Weekly',
    content: 'The Trading Calendar shows upcoming signals so you can plan your week ahead.',
  },
  {
    title: 'Track IPO Exits',
    content: 'Newly listed stocks are risky. Use IPO Exit Timing to know when distribution starts.',
  },
];

export default function HelpPage() {
  const [search, setSearch] = useState('');
  
  const filteredFeatures = features.filter(f => 
    f.title.toLowerCase().includes(search.toLowerCase()) ||
    f.description.toLowerCase().includes(search.toLowerCase()) ||
    f.tags.some(t => t.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <HelpCircle className="h-6 w-6 text-primary" />
            Help & Documentation
          </h1>
          <p className="text-muted-foreground mt-1">
            Learn how to use all the trading tools and features
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search features..."
          className="w-full pl-10 pr-4 py-2.5 bg-surface-1 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50"
        />
      </div>

      {/* Quick Start */}
      <div className="rounded-xl border border-primary/30 bg-primary/10 p-6">
        <h2 className="font-semibold text-lg mb-3 flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-primary" />
          Quick Start Guide
        </h2>
        <div className="grid md:grid-cols-2 gap-3">
          {tips.map((tip, i) => (
            <QuickTip key={i} title={tip.title} content={tip.content} />
          ))}
        </div>
      </div>

      {/* Features */}
      <div>
        <h2 className="text-lg font-semibold mb-4">All Features</h2>
        <div className="space-y-3">
          {filteredFeatures.map((feature, i) => (
            <FeatureCard key={i} {...feature} />
          ))}
        </div>
        
        {filteredFeatures.length === 0 && (
          <div className="rounded-xl border border-border bg-card p-8 text-center">
            <Search className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
            <p className="text-muted-foreground">No features match &quot;{search}&quot;</p>
          </div>
        )}
      </div>

      {/* Trading Tips */}
      <div className="rounded-xl border border-border bg-card p-6">
        <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
          <Settings className="h-5 w-5 text-muted-foreground" />
          Trading Best Practices
        </h2>
        <ul className="space-y-3 text-sm text-muted-foreground">
          <li className="flex items-start gap-2">
            <span className="text-primary font-bold">1.</span>
            <span>Never risk more than 2% of your portfolio on a single trade. Use the position sizing recommendations.</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary font-bold">2.</span>
            <span>Always set a stop loss before entering. The Signal Generator provides suggested stops.</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary font-bold">3.</span>
            <span>NEPSE has T+2 settlement. This tool is for swing trading (5-15 day holds), not day trading.</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary font-bold">4.</span>
            <span>Wait for volume confirmation. A signal without volume is weak.</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary font-bold">5.</span>
            <span>Don&apos;t chase breakouts. Wait for pullbacks to enter at better prices.</span>
          </li>
        </ul>
      </div>

      {/* Disclaimer */}
      <div className="rounded-xl border border-warning/30 bg-warning/10 p-5 text-sm">
        <p className="font-semibold text-warning mb-1">Disclaimer</p>
        <p className="text-muted-foreground">
          This tool is for educational and informational purposes only. It is not financial advice. 
          Past performance does not guarantee future results. Always do your own research and consult 
          a licensed financial advisor before making investment decisions.
        </p>
      </div>
    </div>
  );
}
