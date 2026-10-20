export function AuthShell({ children, side }: { children: React.ReactNode; side?: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <div className="hidden flex-col justify-center border-r border-line bg-gradient-to-br from-[#0f1a33] to-bg p-14 lg:flex">
        <div className="mb-8 text-xl font-extrabold">Axe<span className="text-teal">Algo</span></div>
        {side ?? (
          <>
            <h1 className="text-4xl font-extrabold leading-tight tracking-tight">Every signal with its stop and target.<br />Live, the second it fires.</h1>
            <p className="mt-4 max-w-md text-muted">Gold and crypto signals from a rule-based, non-repainting strategy, delivered in real time to your dashboard, with optional automated execution and a live line to the team.</p>
            <div className="mt-8 flex gap-8">
              <div><div className="text-2xl font-extrabold">~80%</div><div className="text-xs text-muted">winning trades in testing</div></div>
              <div><div className="text-2xl font-extrabold">&lt; 4%</div><div className="text-xs text-muted">max drawdown (backtest)</div></div>
              <div><div className="text-2xl font-extrabold">$20</div><div className="text-xs text-muted">per month, bot access</div></div>
            </div>
            <p className="mt-8 text-xs text-muted">Backtested results are not a promise. No strategy wins every trade.</p>
          </>
        )}
      </div>
      <div className="flex items-center justify-center p-6">
        <div className="card w-full max-w-md !p-8 shadow-card">{children}</div>
      </div>
    </div>
  );
}
