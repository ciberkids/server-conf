### how to install

```bash
sudo cp ./checkNvidiaPodman.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable checkNvidiaPodman.timer
sudo systemctl start checkNvidiaPodman.timerr
```
