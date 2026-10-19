# Dockerfile for CodeIgniter 3 Portal
FROM php:8.2-apache

# Install PDO MySQL, MySQLi, cURL extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4-openssl-dev \
    && docker-php-ext-install pdo pdo_mysql mysqli curl \
    && a2enmod rewrite \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /var/www/html

# Copy CodeIgniter 3 application
COPY portal_ci3/ /var/www/html/

# Permissions
RUN chown -R www-data:www-data /var/www/html

EXPOSE 80

CMD ["apache2-foreground"]
