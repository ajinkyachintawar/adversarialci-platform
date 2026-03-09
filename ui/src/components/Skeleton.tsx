export default function Skeleton({ width, height = 16, borderRadius, count = 1, style }: {
    width?: string | number;
    height?: number;
    borderRadius?: number;
    count?: number;
    style?: React.CSSProperties;
}) {
    return (
        <>
            {Array.from({ length: count }).map((_, i) => (
                <div
                    key={i}
                    className="skeleton"
                    style={{
                        width: width || '100%',
                        height,
                        borderRadius: borderRadius ?? 4,
                        marginBottom: count > 1 && i < count - 1 ? 8 : 0,
                        ...style,
                    }}
                />
            ))}
        </>
    );
}
