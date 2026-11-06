import { Link, useNavigate } from "react-router-dom";
import { Icon } from "@/shared/ui";
import { cn } from "@/core/lib/cn";

export interface BreadcrumbItem {
  label: string;
  href?: string;
  current?: boolean;
}

interface CoursePageHeaderProps {
  breadcrumbs: BreadcrumbItem[];
  title?: string;
  description?: string;
  backHref?: string;
  onBackClick?: () => void;
  actions?: React.ReactNode;
  className?: string;
}

export function CoursePageHeader({
  breadcrumbs,
  title,
  description,
  backHref,
  onBackClick,
  actions,
  className,
}: CoursePageHeaderProps) {
  const navigate = useNavigate();

  const handleBack = () => {
    if (onBackClick) {
      onBackClick();
    } else if (backHref) {
      navigate(backHref);
    } else {
      navigate(-1);
    }
  };

  return (
    <div className={cn("space-y-2 pb-3 border-b border-slate-200", className)}>
      {/* Breadcrumb row & Back button */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center flex-wrap gap-1.5 text-xs text-slate-500 font-medium">
          {(backHref || onBackClick) && (
            <button
              type="button"
              onClick={handleBack}
              className="inline-flex items-center gap-1 text-slate-600 hover:text-[#00663C] mr-2 font-bold cursor-pointer transition-colors"
              title="Go back"
            >
              <Icon name="arrowLeft" size={15} />
              <span>Back</span>
            </button>
          )}

          {breadcrumbs.map((item, index) => {
            const isLast = index === breadcrumbs.length - 1;
            return (
              <div key={index} className="inline-flex items-center gap-1.5">
                {index > 0 && <span className="text-slate-300">/</span>}
                {item.href && !isLast && !item.current ? (
                  <Link
                    to={item.href}
                    className="hover:text-[#00663C] transition-colors truncate max-w-[200px]"
                    title={item.label}
                  >
                    {item.label}
                  </Link>
                ) : (
                  <span
                    className={cn(
                      "truncate max-w-[260px]",
                      isLast || item.current ? "text-slate-900 font-bold" : "text-slate-500"
                    )}
                    title={item.label}
                  >
                    {item.label}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {actions && <div className="flex items-center gap-2.5 shrink-0">{actions}</div>}
      </div>

      {/* Optional Title & Description */}
      {(title || description) && (
        <div className="pt-1">
          {title && <h2 className="text-xl font-bold text-[#0A1530]">{title}</h2>}
          {description && <p className="text-xs text-slate-500 mt-0.5">{description}</p>}
        </div>
      )}
    </div>
  );
}
