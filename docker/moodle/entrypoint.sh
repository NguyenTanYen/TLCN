#!/bin/bash
# Cài Moodle bằng CLI ở lần chạy đầu tiên, các lần sau chỉ khởi động Apache.
set -e
cd /var/www/html
until php -r 'exit(@mysqli_connect(getenv("MOODLE_DB_HOST"), getenv("MOODLE_DB_USER"), getenv("MOODLE_DB_PASS"), "moodle") ? 0 : 1);'; do
  echo "Chờ MySQL…"; sleep 3
done
if [ ! -f config.php ]; then
  su -s /bin/bash www-data -c "php admin/cli/install.php --non-interactive --agree-license --lang=en \
    --wwwroot='$MOODLE_URL' --dataroot=/var/www/moodledata --dbtype=mysqli --dbhost='$MOODLE_DB_HOST' \
    --dbname=moodle --dbuser='$MOODLE_DB_USER' --dbpass='$MOODLE_DB_PASS' --prefix=mdl_ \
    --fullname='HCMUTE Moodle (demo)' --shortname=ute --adminuser=admin --adminpass='$MOODLE_ADMIN_PASS' \
    --adminemail=admin@example.com" || { echo "Cài Moodle thất bại"; exit 1; }
fi
exec "$@"
