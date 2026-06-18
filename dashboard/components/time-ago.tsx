"use client";

import { useState, useEffect } from "react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { relativeTime, formatDateTime } from "@/lib/utils";

export function TimeAgo({ date }: { date: Date | string }) {
  const [, setTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 60_000);
    return () => clearInterval(id);
  }, []);

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="cursor-default">{relativeTime(date)}</span>
        </TooltipTrigger>
        <TooltipContent>
          <p>{formatDateTime(date)}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
