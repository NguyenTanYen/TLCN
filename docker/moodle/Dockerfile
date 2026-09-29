# Moodle 4.5 LTS trên image PHP-Apache chính thức của Moodle HQ
# (image bitnami/moodle đã ngừng cập nhật từ 28/08/2025)
FROM moodlehq/moodle-php-apache:8.3
ARG MOODLE_BRANCH=MOODLE_405_STABLE
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/* \
 && git clone --depth 1 -b ${MOODLE_BRANCH} https://github.com/moodle/moodle.git /var/www/html \
 && mkdir -p /var/www/moodledata && chown -R www-data:www-data /var/www/html /var/www/moodledata \
 && echo "max_input_vars = 5000" > /usr/local/etc/php/conf.d/99-moodle.ini
COPY entrypoint.sh /usr/local/bin/moodle-entrypoint.sh
RUN chmod +x /usr/local/bin/moodle-entrypoint.sh
ENTRYPOINT ["moodle-entrypoint.sh"]
CMD ["apache2-foreground"]
