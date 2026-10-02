import { useRef, useState } from "react";
import { useNavigate } from "react-router";
import { SECRET_PATH, unlockSecret } from "../lib/secret";
import { ClockIcon } from "./Icons";

const CLICKS = 10;
/**
 * Clicks further apart than this start the count again, so the sequence has to be deliberate
 * rather than accumulated across a visit. Three seconds is still a long pause for someone
 * clicking on purpose (real gaps are a few hundred milliseconds), while leaving enough headroom
 * that a slow frame doesn't silently reset a genuine attempt.
 */
const GAP_MS = 3000;

/**
 * The clock beside "Re-checked automatically" in a match's sources block. Ten clicks open the
 * hidden page; each one turns the clock a tenth of a full circle, so it completes exactly one
 * revolution on the last click.
 *
 * It stays decorative for assistive technology: the sentence next to it already carries the
 * meaning, and nothing here is functionality anyone needs to reach.
 */
export function SecretClock({ size = 15 }: { size?: number }) {
  const [count, setCount] = useState(0);
  const last = useRef(0);
  const navigate = useNavigate();

  const onClick = () => {
    const now = Date.now();
    const next = now - last.current > GAP_MS ? 1 : count + 1;
    last.current = now;
    if (next >= CLICKS) {
      setCount(0);
      unlockSecret();
      navigate(SECRET_PATH);
      return;
    }
    setCount(next);
  };

  return (
    <span
      onClick={onClick}
      data-tick={count}
      className="inline-flex select-none transition-transform duration-200 ease-out motion-reduce:transition-none"
      style={{ transform: `rotate(${count * (360 / CLICKS)}deg)` }}
    >
      <ClockIcon size={size} />
    </span>
  );
}
