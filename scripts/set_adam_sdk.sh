cd "$(dirname "$0")"
cd ..

adam_robot_path="reference/adam/adam-robot"

if [ -d "$adam_robot_path" ];then
  echo ">>> $adam_robot_path exist, git checkout code then git pull"
  git -C "$adam_robot_path" checkout .
  git -C "$adam_robot_path" pull
else
  echo ">>> $adam_robot_path not exist, git clone code"
  git clone -b master https://gitee.com/richtechrobots/adam-robot.git reference/adam/adam-robot
fi

echo ">>> cp adam_sdk to adam module"
cp -r reference/adam/adam-robot/adam_sdk adam
echo ">>> delete $adam_robot_path"
rm -rf $adam_robot_path