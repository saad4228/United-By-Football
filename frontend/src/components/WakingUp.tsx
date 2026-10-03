import { useEffect, useState } from "react";
import { t } from "../lib/i18n";
import { BallIcon } from "./Icons";

/**
 * Shown while the first load is still waiting on data.
 *
 * It holds off for a couple of seconds first: a quick load should never flash a message about
 * waiting, and most loads are quick. It only earns its place on the slow ones — typically the
 * first visit after the free instance has been idle.
 */
export function WakingUp({ after = 2500, className = "container-x" }: { after?: number; className?: string }) {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const id = window.setTimeout(() => setShow(true), after);
    return () => window.clearTimeout(id);
  }, [after]);
  if (!show) return null;
  return (
    <div
      role="status"
      className={`${className} flex flex-col items-center gap-3 pb-2 pt-12 text-center sm:pt-16`}
    >
      <span className="text-fg-2 motion-safe:animate-[spin_2.4s_linear_infinite]">
        <BallIcon size={26} />
      </span>
      <span className="text-[18px] font-bold">{t("loading.title")}</span>
      <span className="max-w-md text-[15px] leading-relaxed text-muted">{t("loading.body")}</span>
    </div>
  );
}
