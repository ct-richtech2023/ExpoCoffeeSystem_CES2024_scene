cd $(dirname $0)
echo your system: `uname -s`
cd ..
uname -s | grep NT
if [ $? -eq 0 ];then
  project_dir=`cygpath -w $(pwd)`
  winpty='winpty'
else
  project_dir=`pwd`
  winpty=''
fi
echo project_dir path: $project_dir

port=9090

$winpty docker run -it --rm -v $project_dir:/docs --name CoffeeRoomDocs -p $port:$port m986883511/sphinx:all sphinx-autobuild docs/source docs/build --port $port --host 0.0.0.0