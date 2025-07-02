# Use a lightweight Nginx image to serve static files
FROM nginx:alpine

# Copy the frontend application files to the Nginx web root
# The 'dist' directory is commonly used for built frontend assets,
# but since this is a simple HTML file, we copy directly.
COPY . /usr/share/nginx/html

# Expose port 80, which Nginx listens on by default
EXPOSE 80

# Command to run Nginx in the foreground
CMD ["nginx", "-g", "daemon off;"]
