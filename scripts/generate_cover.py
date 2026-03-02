import argparse
import os
import urllib.parse
import urllib.request
import ssl

# Disable SSL for compatibility
ssl._create_default_https_context = ssl._create_unverified_context

def generate_online_png(title, style_name, output_path):
    """
    Generate a high-quality PNG cover using placehold.jp API.
    Supports Chinese characters and custom styling.
    """
    # Style configurations matching our project
    styles = {
        "swiss": {"bg": "ffffff", "text": "000000", "fontsize": "60"},
        "terminal": {"bg": "0d1117", "text": "39d353", "fontsize": "50"},
        "cyber": {"bg": "0a0f1c", "text": "00ffcc", "fontsize": "50"},
        "bold": {"bg": "1a1a1a", "text": "ff5722", "fontsize": "60"},
        "botanical": {"bg": "0f0f0f", "text": "d4a574", "fontsize": "50"}
    }
    
    s = styles.get(style_name, styles["swiss"])
    
    # Construct placehold.jp URL
    # Format: https://placehold.jp/{font-size}/{bg-color}/{text-color}/{width}x{height}.png?text={content}
    encoded_title = urllib.parse.quote(title)
    url = f"https://placehold.jp/{s['fontsize']}/{s['bg']}/{s['text']}/900x383.png?text={encoded_title}"
    
    print(f"Requesting cover from: {url}")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            with open(output_path, "wb") as f:
                f.write(response.read())
        return True
    except Exception as e:
        print(f"Online generation failed: {e}")
        return False

def generate_fallback_svg(title, style_name, output_path):
    # Simplified SVG generator if online service is down
    bg = "#0d1117" if style_name == "terminal" else "#ffffff"
    text = "#39d353" if style_name == "terminal" else "#000000"
    
    svg = f"""<svg width="900" height="383" xmlns="http://www.w3.org/2000/svg">
        <rect width="900" height="383" fill="{bg}"/>
        <text x="50%" y="50%" font-family="Arial" font-size="50" fill="{text}" text-anchor="middle" dominant-baseline="middle">{title}</text>
    </svg>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg)

def main():
    parser = argparse.ArgumentParser(description="Generate Branded Article Cover")
    parser.add_argument("--title", required=True, help="Article Title")
    parser.add_argument("--style", default="swiss")
    parser.add_argument("--output", default="assets/cover.png")
    
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # Try PNG first, then SVG fallback
    success = generate_online_png(args.title, args.style, args.output)
    
    if not success:
        svg_path = args.output.replace(".png", ".svg")
        generate_fallback_svg(args.title, args.style, svg_path)
        print(f"Fallback to SVG: {svg_path}")
    else:
        print(f"Success! Branded PNG cover generated at {args.output}")

if __name__ == "__main__":
    main()
