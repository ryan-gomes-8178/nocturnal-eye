"""
Visualizer - Heatmap and visualization generation
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime
from PIL import Image

logger = logging.getLogger(__name__)


class HeatmapGenerator:
    """Generates heatmaps from activity data"""
    
    def __init__(self, config: dict):
        self.config = config
        self.grid_size = config['heatmap'].get('grid_size', 50)
        self.colormap = config['heatmap'].get('colormap', 'COLORMAP_JET')
        self.overlay_alpha = config['heatmap'].get('overlay_alpha', 0.6)
        self.output_dir = Path(config.get('static', {}).get('heatmaps', 'static/heatmaps'))
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"HeatmapGenerator initialized: grid_size={self.grid_size}")
    
    def generate_heatmap(
        self,
        points: List[Tuple[int, int]],
        frame_size: Tuple[int, int] = (640, 480),
        background_image: Optional[np.ndarray] = None,
        title: str = "Activity Heatmap"
    ) -> np.ndarray:
        """
        Generate a heatmap from position data
        
        Args:
            points: List of (x, y) coordinates
            frame_size: Size of the frame (width, height)
            background_image: Optional background image to overlay on
            title: Title for the heatmap
            
        Returns:
            Heatmap image as numpy array
        """
        if not points:
            logger.warning("No points provided for heatmap generation")
            # Return blank image
            return np.zeros((frame_size[1], frame_size[0], 3), dtype=np.uint8)
        
        width, height = frame_size
        
        # Create 2D histogram (heatmap grid)
        heatmap = np.zeros((height, width), dtype=np.float32)
        
        # Count occurrences at each position
        for x, y in points:
            if 0 <= x < width and 0 <= y < height:
                heatmap[y, x] += 1
        
        # Apply Gaussian blur for smooth heatmap
        kernel_size = self.grid_size
        if kernel_size % 2 == 0:
            kernel_size += 1
        heatmap = cv2.GaussianBlur(heatmap, (kernel_size, kernel_size), 0)
        
        # Normalize to 0-255
        if heatmap.max() > 0:
            heatmap = (heatmap / heatmap.max() * 255).astype(np.uint8)
        else:
            heatmap = heatmap.astype(np.uint8)
        
        # Apply colormap
        colormap_id = getattr(cv2, self.colormap, cv2.COLORMAP_JET)
        heatmap_colored = cv2.applyColorMap(heatmap, colormap_id)
        
        # Overlay on background if provided
        if background_image is not None:
            # Resize background to match frame size
            if background_image.shape[:2] != (height, width):
                background_image = cv2.resize(background_image, (width, height))
            
            # Blend images
            result = cv2.addWeighted(
                background_image,
                1 - self.overlay_alpha,
                heatmap_colored,
                self.overlay_alpha,
                0
            )
        else:
            result = heatmap_colored
        
        # Add title
        cv2.putText(
            result,
            title,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2
        )
        
        # Add legend info
        info_text = f"Total points: {len(points)}"
        cv2.putText(
            result,
            info_text,
            (10, height - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )
        
        return result
    
    def save_heatmap(
        self,
        heatmap: np.ndarray,
        filename: str = None,
        date: datetime = None
    ) -> Path:
        """
        Save heatmap to file
        
        Args:
            heatmap: Heatmap image
            filename: Output filename (auto-generated if None)
            date: Date for filename generation
            
        Returns:
            Path to saved file
        """
        if filename is None:
            date_str = date.strftime('%Y-%m-%d') if date else datetime.now().strftime('%Y-%m-%d')
            filename = f"heatmap_{date_str}.png"
        
        output_path = self.output_dir / filename
        
        # Save using OpenCV
        cv2.imwrite(str(output_path), heatmap)
        
        logger.info(f"Heatmap saved: {output_path}")
        return output_path
    
    def generate_matplotlib_heatmap(
        self,
        points: List[Tuple[int, int]],
        frame_size: Tuple[int, int] = (640, 480),
        title: str = "Activity Heatmap",
        filename: str = None
    ) -> Path:
        """
        Generate high-quality heatmap using matplotlib
        
        Args:
            points: List of (x, y) coordinates
            frame_size: Size of the frame
            title: Title for the plot
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        if not points:
            logger.warning("No points provided for matplotlib heatmap")
            return None
        
        width, height = frame_size
        
        # Extract x and y coordinates
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 9))
        
        # Create 2D histogram
        heatmap, xedges, yedges = np.histogram2d(
            x_coords, y_coords,
            bins=[width // self.grid_size, height // self.grid_size],
            range=[[0, width], [0, height]]
        )
        
        # Plot heatmap
        im = ax.imshow(
            heatmap.T,
            origin='lower',
            extent=[0, width, 0, height],
            cmap='hot',
            interpolation='gaussian',
            aspect='auto'
        )
        
        # Add colorbar
        plt.colorbar(im, ax=ax, label='Activity Intensity')
        
        # Labels and title
        ax.set_xlabel('X Position (pixels)')
        ax.set_ylabel('Y Position (pixels)')
        ax.set_title(title)
        
        # Grid
        ax.grid(True, alpha=0.3)
        
        # Save figure
        if filename is None:
            filename = f"heatmap_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png"
        
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Matplotlib heatmap saved: {output_path}")
        return output_path


class ActivityVisualizer:
    """Visualizes activity data and statistics"""
    
    def __init__(self, config: dict):
        self.config = config
        self.output_dir = Path('static/visualizations')
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def plot_hourly_activity(
        self,
        hourly_data: dict,
        date: datetime,
        filename: str = None
    ) -> Path:
        """
        Plot hourly activity distribution
        
        Args:
            hourly_data: Dictionary of {hour: count}
            date: Date of the data
            filename: Output filename
            
        Returns:
            Path to saved plot
        """
        hours = sorted(hourly_data.keys())
        counts = [hourly_data[h] for h in hours]
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        ax.bar(hours, counts, color='steelblue', edgecolor='black')
        
        ax.set_xlabel('Hour of Day')
        ax.set_ylabel('Activity Count')
        ax.set_title(f'Hourly Activity Distribution - {date.strftime("%Y-%m-%d")}')
        ax.set_xticks(hours)
        ax.grid(True, alpha=0.3, axis='y')
        
        # Highlight nighttime hours (20:00 - 08:00)
        for hour in hours:
            if hour >= 20 or hour <= 8:
                ax.axvspan(hour - 0.4, hour + 0.4, alpha=0.2, color='navy')
        
        if filename is None:
            filename = f"hourly_activity_{date.strftime('%Y-%m-%d')}.png"
        
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Hourly activity plot saved: {output_path}")
        return output_path
    
    def plot_weekly_trend(
        self,
        daily_counts: dict,
        filename: str = "weekly_trend.png"
    ) -> Path:
        """
        Plot weekly activity trend
        
        Args:
            daily_counts: Dictionary of {date_string: count}
            filename: Output filename
            
        Returns:
            Path to saved plot
        """
        dates = sorted(daily_counts.keys())
        counts = [daily_counts[d] for d in dates]
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(dates, counts, marker='o', linewidth=2, markersize=8, color='darkgreen')
        ax.fill_between(range(len(dates)), counts, alpha=0.3, color='lightgreen')
        
        ax.set_xlabel('Date')
        ax.set_ylabel('Total Activity Events')
        ax.set_title('Weekly Activity Trend')
        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates, rotation=45, ha='right')
        ax.grid(True, alpha=0.3)
        
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Weekly trend plot saved: {output_path}")
        return output_path


if __name__ == "__main__":
    # Test visualizer
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    config = {
        'heatmap': {
            'grid_size': 50,
            'colormap': 'COLORMAP_JET',
            'overlay_alpha': 0.6
        },
        'static': {
            'heatmaps': 'static/heatmaps'
        }
    }
    
    generator = HeatmapGenerator(config)
    
    # Generate test data
    np.random.seed(42)
    test_points = [
        (int(np.random.normal(320, 100)), int(np.random.normal(240, 80)))
        for _ in range(500)
    ]
    
    # Generate heatmap
    heatmap = generator.generate_heatmap(test_points, title="Test Heatmap")
    output_path = generator.save_heatmap(heatmap, "test_heatmap.png")
    
    logger.info(f"Test heatmap generated: {output_path}")
