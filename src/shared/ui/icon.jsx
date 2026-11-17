/** Named steps of the icon size scale, in pixels. Numbers and CSS lengths are accepted too. */
const ICON_SIZES = { sm: 16, md: 20, lg: 24, xl: 32 };

const ICON_BASE_STYLE = { display: "inline-block", flexShrink: 0, verticalAlign: "middle" };

/**
 * Renders a Tabler icon (`@tabler/icons-react`) with the app's defaults: the size scale,
 * a 1.75 stroke and accessibility. Without `label` the icon is decorative and hidden from
 * screen readers; with it the icon is announced as an image.
 */
export default function Icon({
  icon: TablerIcon,
  size = "md",
  stroke = 1.75,
  label,
  className,
  style,
  ...rest
}) {
  return (
    <TablerIcon
      size={ICON_SIZES[size] ?? size}
      stroke={stroke}
      title={label}
      aria-hidden={label ? undefined : true}
      role={label ? "img" : undefined}
      className={className}
      style={style ? { ...ICON_BASE_STYLE, ...style } : ICON_BASE_STYLE}
      {...rest}
    />
  );
}
