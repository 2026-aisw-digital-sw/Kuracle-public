import { BottomNav, SideNav } from "@/components/nav";

export default function ShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-full">
      <SideNav />
      <main className="flex-1 flex flex-col min-h-0 pb-[56px] md:pb-0 overflow-hidden">
        {children}
      </main>
      <BottomNav />
    </div>
  );
}
