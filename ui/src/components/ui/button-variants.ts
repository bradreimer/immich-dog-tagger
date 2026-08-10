import { cva } from "class-variance-authority";

export const buttonVariants = cva(
  "action-button inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md border text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "border-primary bg-primary text-primary-foreground shadow-sm hover:bg-primary/90",
        destructive: "border-primary bg-primary text-primary-foreground shadow-sm hover:bg-primary/90",
        outline: "border-primary/45 bg-primary/12 text-primary hover:bg-primary/20 dark:text-primary-foreground",
        secondary: "border-primary/60 bg-primary/80 text-primary-foreground shadow-sm hover:bg-primary/70",
        ghost: "border-primary/35 bg-primary/8 text-primary hover:bg-primary/18 dark:text-primary-foreground",
        link: "border-transparent bg-transparent text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 px-3",
        lg: "h-11 px-5",
        icon: "size-10 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);