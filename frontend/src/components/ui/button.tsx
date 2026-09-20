import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { cn } from "@/lib/utils";

// shadcn/ui's Button, unedited except that every value below is a theme token rather than a stock neutral.
// That is the whole point of the theme layer: components come from shadcn and inherit the look untouched.
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-sm text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:text-text-disabled [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-text-2",
        secondary: "bg-secondary text-secondary-foreground hover:bg-border",
        outline: "border border-border-control bg-transparent text-text-2 hover:bg-secondary hover:text-text-1",
        ghost: "text-text-2 hover:bg-secondary hover:text-text-1",
        destructive: "bg-destructive text-destructive-foreground hover:brightness-110",
      },
      size: {
        // --f1-control-h is 34px, the height every control in the dashboard shares.
        default: "h-[var(--f1-control-h)] px-4",
        sm: "h-7 px-3 text-xs",
        icon: "h-[var(--f1-control-h)] w-[var(--f1-control-h)]",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}

export { buttonVariants };
