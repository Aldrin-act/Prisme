export function PrismeLogo({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <img
      src="/logo.png"
      alt="PRISME"
      className={`${className} object-contain drop-shadow-[0_0_20px_rgba(139,92,246,0.35)]`}
    />
  );
}

export function PrismeWordmark({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <PrismeLogo className="h-9 w-9" />
      <span className="text-lg font-bold tracking-tight">PRISME</span>
    </div>
  );
}
