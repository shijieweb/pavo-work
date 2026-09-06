import { useState } from 'react';
import { Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export default function SearchBar({ value, onChange, placeholder = '搜索项目...', className }: SearchBarProps) {
  const [focused, setFocused] = useState(false);

  const handleClear = () => {
    onChange('');
  };

  return (
    <div
      className={cn(
        'relative flex items-center',
        'w-full max-w-md',
        'transition-all duration-150 ease-standard',
        className
      )}
    >
      <Search
        className={cn(
          'absolute left-3 w-4 h-4',
          'transition-colors duration-150',
          focused ? 'text-accent' : 'text-meta'
        )}
        aria-hidden="true"
      />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder={placeholder}
        className={cn(
          'w-full pl-9 pr-9 py-2',
          'text-sm text-fg',
          'bg-surface border border-border',
          'rounded-sm focus:outline-none focus:border-accent',
          'transition-colors duration-150',
          'placeholder:text-meta'
        )}
        aria-label="搜索项目"
      />
      {value && (
        <button
          onClick={handleClear}
          className={cn(
            'absolute right-2 p-1',
            'text-meta hover:text-fg',
            'transition-colors duration-150',
            'rounded-sm focus:outline-none focus:ring-2 focus:ring-accent focus:ring-opacity-30'
          )}
          aria-label="清除搜索"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
